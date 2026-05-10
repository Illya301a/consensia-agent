import os
import time
from datetime import datetime, timedelta, timezone
import re
import gc
import json
import random
import asyncio
import logging
import requests
import torch
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pyrogram import Client, filters
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from pydantic import BaseModel
from web3 import Web3

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

# ML Configurations
TAGGER_BASE = "Qwen/Qwen2.5-1.5B-Instruct"
ANALYZER_BASE = "Qwen/Qwen2.5-3B-Instruct" 
TAGGER_LORA = "tagger_1_5B_lora_final"
ANALYZER_LORA = "analyzer_3B_lora_final"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Telegram and Web3 Setup
API_ID = os.getenv("USERBOT_API_ID")
API_HASH = os.getenv("USERBOT_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALERT_CHAT_ID = int(os.getenv("ALERT_CHAT_ID", 0))

app_bot = Client("consensia_userbot", api_id=API_ID, api_hash=API_HASH)
notifier_bot = Client("notifier_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Connect to Ethereum Mainnet (Public Ankr node)
w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/eth'))

# State Management and WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_log(self, message: str):
        logger.info(f"UI LOG: {message}")
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()
is_agent_running = False
monitored_channels = [] 
ml_processing_queue = asyncio.Queue()

# Blockchain Search Integration
def python_blockchain_search(params: dict) -> str:
    BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY")
    if not BITQUERY_API_KEY:
        logger.error("BITQUERY_API_KEY not found in environment variables.")
        return "No matching transactions found."

    network = params.get("network", "ethereum").lower()
    min_amount = float(params.get("min_amount", 0)) if params.get("min_amount") else 0.0
    asset_symbol = (params.get("asset") or "ETH").upper()
    time_window = params.get("time_window", "last_24_hours")

    network_map = {
        "ethereum": "ethereum",
        "bsc": "bsc",
        "polygon": "matic",
        "arbitrum": "arbitrum",
        "optimism": "optimism",
        "avalanche": "avalanche"
    }
    
    bq_network = network_map.get(network)
    if not bq_network:
        logger.warning(f"Network '{network}' is currently not supported by Bitquery.")
        return "No matching transactions found."

    now = datetime.now(timezone.utc)
    if time_window == "last_7_days":
        start_time = now - timedelta(days=7)
    else:
        start_time = now - timedelta(days=1)

    since_iso = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    logger.info(f"Bitquery search: {bq_network}, amount >= {min_amount} {asset_symbol}, since {since_iso}")

    query = """
    query ($network: EthereumNetwork!, $time_ago: ISO8601DateTime, $min_amount: Float, $symbol: String) {
      ethereum(network: $network) {
        transfers(
          options: {desc: "block.timestamp.time", limit: 1}
          time: {since: $time_ago}
          amount: {ge: $min_amount}
          currency: {symbol: {is: $symbol}}
        ) {
          transaction { hash }
          sender { address }
          receiver { address }
          amount
          currency { symbol }
        }
      }
    }
    """
    
    variables = {
        "network": bq_network,
        "time_ago": since_iso,
        "min_amount": min_amount,
        "symbol": asset_symbol
    }

    try:
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": BITQUERY_API_KEY
        }
        
        response = requests.post(
            "https://graphql.bitquery.io", 
            json={'query': query, 'variables': variables}, 
            headers=headers,
            timeout=15
        )
        
        if response.status_code != 200:
            logger.error(f"Bitquery API error: {response.status_code} - {response.text}")
            return "No matching transactions found."
            
        data = response.json()
        
        if "errors" in data:
            logger.error(f"GraphQL error: {data['errors']}")
            return "No matching transactions found."

        transfers = data.get('data', {}).get('ethereum', {}).get('transfers', [])
        
        if transfers and len(transfers) > 0:
            tx = transfers[0]
            tx_hash = tx['transaction']['hash']
            sender = tx['sender']['address']
            receiver = tx['receiver']['address']
            amount = tx['amount']
            currency = tx['currency']['symbol']
            
            result_str = (
                f"Transaction_ID: {tx_hash}, "
                f"Sender_Address: {sender}, "
                f"Receiver_Address: {receiver}, "
                f"Amount: {amount:.8f}, "
                f"Asset: {currency}, "
                f"Status: Confirmed"
            )
            
            logger.info(f"Blockchain match found: {tx_hash}")
            return result_str
        else:
            logger.info("No transactions found matching the criteria.")
            return "No matching transactions found."
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during Bitquery request: {e}")
        return "No matching transactions found."
    except Exception as e:
        logger.error(f"Internal error in python_blockchain_search: {e}")
        return "No matching transactions found."

# Web3 Data Enrichment
def enrich_alert_with_bounties(original_text: str) -> str:
    """Enriches alert data with ENS resolution and Sourcify contract verification."""
    enrichment_log = []
    
    eth_addresses = re.findall(r'(0x[a-fA-F0-9]{40})', original_text, re.IGNORECASE)
    ens_names = re.findall(r'([a-zA-Z0-9-]+\.eth)', original_text, re.IGNORECASE)
    
    unique_addresses = set(addr.lower() for addr in eth_addresses)

    try:
        if w3.is_connected():
            # ENS Resolution
            for ens in set(ens_names):
                resolved_addr = w3.ens.address(ens)
                if resolved_addr:
                    enrichment_log.append(f"ENS Resolved: `{ens}` -> `{resolved_addr}`")
                    unique_addresses.add(resolved_addr.lower())

            # Sourcify Check & Reverse ENS
            for addr in unique_addresses:
                checksum_addr = w3.to_checksum_address(addr)
                
                # Reverse ENS
                reverse_ens = w3.ens.name(checksum_addr)
                if reverse_ens:
                    enrichment_log.append(f"Hacker ENS: Address `{checksum_addr}` belongs to `{reverse_ens}`")
                
                # Sourcify Verification
                code = w3.eth.get_code(checksum_addr)
                if code != b'':
                    try:
                        resp = requests.get(f"https://sourcify.dev/server/checkByAddresses?addresses={checksum_addr}&chainIds=1", timeout=5).json()
                        if resp and isinstance(resp, list) and resp[0].get("status") == "perfect":
                            enrichment_log.append(f"Sourcify: Contract `{checksum_addr}` is FULLY VERIFIED (Safe).")
                        else:
                            enrichment_log.append(f"Sourcify: Contract `{checksum_addr}` is UNVERIFIED (High Risk).")
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"Data enrichment error: {e}")

    if enrichment_log:
        return "\n\n**On-Chain Analysis (Sentinel Python):**\n" + "\n".join(enrichment_log)
    return ""

# ML Pipeline Core Functions
def clean_input_text(text):
    text = re.sub(r'\\n|\n', ' ', text)
    text = re.sub(r'https?:\/\/\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text) 
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_response(model, tokenizer, instruction, input_text, device=DEVICE):
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": input_text}
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(device)
    
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=256, temperature=0.1, pad_token_id=tokenizer.eos_token_id)
    generated_ids = outputs[0][inputs.input_ids.shape[-1]:]
    return tokenizer.decode(generated_ids, skip_special_tokens=True)

def free_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def run_ml_pipeline_sync(raw_text: str, loop: asyncio.AbstractEventLoop):
    filtered_text = clean_input_text(raw_text)
    
    # Stage 1: L1 Tagger
    asyncio.run_coroutine_threadsafe(manager.broadcast_log("[STAGE 1] Loading L1 (1.5B)..."), loop)
    tokenizer_1 = AutoTokenizer.from_pretrained(TAGGER_BASE)
    base_model_1 = AutoModelForCausalLM.from_pretrained(TAGGER_BASE, device_map=DEVICE, dtype=torch.float16)
    tagger_model = PeftModel.from_pretrained(base_model_1, TAGGER_LORA)
    
    instruction_1 = "Clean text, remove spam, extract tags."
    tagger_output = generate_response(tagger_model, tokenizer_1, instruction_1, f"Content: {filtered_text}")
    
    del tagger_model, base_model_1, tokenizer_1
    free_memory()

    if "DROP_NOISE" in tagger_output:
        asyncio.run_coroutine_threadsafe(manager.broadcast_log("L1: DROP_NOISE. Discarded."), loop)
        return False, None

    # Stage 2: L2 Analyzer (First Pass)
    asyncio.run_coroutine_threadsafe(manager.broadcast_log("[STAGE 2] Loading L2 (3B) for strategy analysis..."), loop)
    tokenizer_2 = AutoTokenizer.from_pretrained(ANALYZER_BASE)
    base_model_2 = AutoModelForCausalLM.from_pretrained(ANALYZER_BASE, device_map=DEVICE, dtype=torch.float16)
    analyzer_model = PeftModel.from_pretrained(base_model_2, ANALYZER_LORA)
    
    instruction_2 = "Analyze content and determine strategy."
    analyzer_output_1 = generate_response(analyzer_model, tokenizer_2, instruction_2, tagger_output)
    
    strategy_json = extract_json(analyzer_output_1)
    
    if not strategy_json:
        del analyzer_model, base_model_2, tokenizer_2
        free_memory()
        return False, None

    action = strategy_json.get("action")
    
    if action in ["DROP_CONTEXT", "REQUEST_CONTEXT"]:
        del analyzer_model, base_model_2, tokenizer_2
        free_memory()
        asyncio.run_coroutine_threadsafe(manager.broadcast_log(f"L2: {action}. No threat detected or missing data."), loop)
        return False, None

    elif action == "SEARCH_BLOCKCHAIN":
        params = strategy_json.get("params", {})
        asyncio.run_coroutine_threadsafe(manager.broadcast_log(f"L2 requested blockchain search with params: {params}"), loop)
        
        blockchain_result = python_blockchain_search(params)
        
        # Stage 3: L2 Analyzer (Verification)
        instruction_3 = "Verify blockchain data against the reported event."
        input_3 = f"Content: {filtered_text}\nBlockchain: {blockchain_result}"
        
        asyncio.run_coroutine_threadsafe(manager.broadcast_log("[STAGE 3] L2 verifying found transactions..."), loop)
        analyzer_output_2 = generate_response(analyzer_model, tokenizer_2, instruction_3, input_3)
        
        verification_json = extract_json(analyzer_output_2)
        
        del analyzer_model, base_model_2, tokenizer_2
        free_memory()

        if verification_json and verification_json.get("action") == "SEND_TELEGRAM_ALERT":
            return True, verification_json.get("summary", "Confirmed threat found!")
        else:
            asyncio.run_coroutine_threadsafe(manager.broadcast_log("L2: Blockchain data did not verify the threat (DROP_CONTEXT)."), loop)
            return False, None

    elif action == "SEND_TELEGRAM_ALERT":
        del analyzer_model, base_model_2, tokenizer_2
        free_memory()
        return True, strategy_json.get("summary", "Critical threat detected!")

    del analyzer_model, base_model_2, tokenizer_2
    free_memory()
    return False, None

# Async Worker
async def ml_worker():
    loop = asyncio.get_running_loop()
    while True:
        message_text, chat_title = await ml_processing_queue.get()
        await manager.broadcast_log(f"Started processing message from {chat_title}")
        
        try:
            passed, summary = await asyncio.to_thread(run_ml_pipeline_sync, message_text, loop)
            
            if passed:
                await manager.broadcast_log("ALERT: Verified! ML finished. Triggering Python script for ENS/Sourcify...")
                extra_onchain_data = await asyncio.to_thread(enrich_alert_with_bounties, message_text)
                
                alert_msg = (
                    f"**SENTINEL VERIFIED ALERT**\n\n"
                    f"**Source:** {chat_title}\n\n"
                    f"**Analyzer Conclusion:**\n{summary}{extra_onchain_data}"
                )
                
                if ALERT_CHAT_ID:
                    await notifier_bot.send_message(chat_id=ALERT_CHAT_ID, text=alert_msg)
        except Exception as e:
            await manager.broadcast_log(f"ML pipeline error: {str(e)}")
        finally:
            ml_processing_queue.task_done()

# Telegram Message Handler
@app_bot.on_message(filters.channel | filters.group)
async def handle_new_message(client, message):
    if not is_agent_running:
        return
        
    chat_id = str(message.chat.id)
    if monitored_channels and chat_id not in monitored_channels:
        return

    text = message.text or message.caption
    if not text:
        return
        
    chat_title = message.chat.title or message.chat.username or "Unknown Chat"
    await manager.broadcast_log(f"New post from {chat_title}. Added to queue.")
    await ml_processing_queue.put((text, chat_title))

# FastAPI Configuration and Endpoints
class SettingsPayload(BaseModel):
    channels: list[str]

@asynccontextmanager
async def lifespan(app: FastAPI):
    await app_bot.start()
    await notifier_bot.start()
    worker_task = asyncio.create_task(ml_worker())
    yield
    await app_bot.stop()
    await notifier_bot.stop()
    worker_task.cancel()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/toggle")
async def toggle_agent():
    global is_agent_running
    is_agent_running = not is_agent_running
    state = "STARTED" if is_agent_running else "STOPPED"
    await manager.broadcast_log(f"Agent {state}")
    return {"status": "success", "running": is_agent_running}

@app.get("/api/status")
async def get_status():
    return {"running": is_agent_running}

@app.post("/api/settings")
async def save_settings(payload: SettingsPayload):
    global monitored_channels
    monitored_channels = payload.channels
    await manager.broadcast_log(f"Updated monitored channels list: {len(monitored_channels)} items.")
    return {"status": "success", "monitored": monitored_channels}

@app.get("/api/sources")
async def get_sources():
    tg_sources = []
    try:
        async for dialog in app_bot.get_dialogs(limit=100):
            if dialog.chat.type.value in ["channel", "supergroup"]:
                tg_sources.append({
                    "id": str(dialog.chat.id),
                    "name": dialog.chat.title,
                    "username": dialog.chat.username or ""
                })
    except Exception as e:
        logger.error(f"Error fetching dialogs: {e}")
    return {"telegram": tg_sources}

# Frontend Serving (React)
if os.path.exists("dist"):
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

    @app.get("/{catchall:path}")
    async def serve_react_app(catchall: str):
        if catchall.startswith("api/") or catchall.startswith("ws/"):
            return None
        return FileResponse("dist/index.html")
else:
    logger.warning("Directory 'dist' not found. Frontend will not be served. Run 'npm run build'.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
