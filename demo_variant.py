import os
import time
from datetime import datetime, timedelta, timezone
import re
import gc
import json
import random
import asyncio
import logging
import csv
import torch
from pyrogram import Client
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from web3 import Web3

load_dotenv()

# Configure logging, but silence chatty external libraries
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger(os.name)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("filelock").setLevel(logging.WARNING)
for _lg in (
    "pyrogram",
    "pyrogram.session",
    "pyrogram.session.session",
    "pyrogram.connection",
    "pyrogram.dispatcher",
):
    logging.getLogger(_lg).setLevel(logging.CRITICAL)

# ML Configurations
TAGGER_BASE = "Qwen/Qwen2.5-1.5B-Instruct"
ANALYZER_BASE = "Qwen/Qwen2.5-3B-Instruct" 
TAGGER_LORA = "itsSHAS/consensia-tagger-1.5b-lora"
ANALYZER_LORA = "itsSHAS/consensia-analyzer_3B_lora_final"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Telegram and Web3 Setup
API_ID = os.getenv("USERBOT_API_ID")
API_HASH = os.getenv("USERBOT_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALERT_CHAT_ID = int(os.getenv("ALERT_CHAT_ID", 0))

if not all([API_ID, API_HASH, BOT_TOKEN, ALERT_CHAT_ID]):
    logger.error("Missing required environment variables. Please check your .env file.")
    exit(1)

# If L3 withholds SEND_TELEGRAM_ALERT but L2 ran SEARCH_BLOCKCHAIN and the offline CSV matched, still send a demo Telegram ping
NOTIFY_ON_OFFLINE_CHAIN_MATCH = os.getenv(
    "DEMO_NOTIFY_ON_CHAIN_MATCH", "1"
).strip().lower() in ("1", "true", "yes", "on")

# Connect to Ethereum Mainnet (Public Ankr node)
w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/eth'))

# ==========================================
# 1. LOCAL BLOCKCHAIN SEARCH
# ==========================================
NO_MATCH = "No matching transactions found."


def python_blockchain_search(params: dict) -> tuple[str, bool]:
    """Searches for transactions in the generated CSV file. Returns (summary_text, matched)."""
    min_amount = float(params.get("min_amount", 0)) if params.get("min_amount") else 0.0
    asset_symbol = (params.get("asset") or "ETH").upper()

    logger.info(f"Offline CSV Search: amount >= {min_amount} {asset_symbol}")

    try:
        with open("demo_blockchain_db.csv", mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Currency"].upper() == asset_symbol:
                    if float(row["Amount"]) >= min_amount:
                        result_str = (
                            f"Transaction_ID: {row['Transaction_ID']}, "
                            f"Sender_Address: {row['Sender_Address']}, "
                            f"Receiver_Address: {row['Receiver_Address']}, "
                            f"Amount: {float(row['Amount']):.8f}, "
                            f"Asset: {row['Currency']}, "
                            f"Status: {row['Transaction_Status']}"
                        )
                        logger.info(f"Mock Blockchain match found: {row['Transaction_ID']}")
                        return result_str, True
                        
    except FileNotFoundError:
        logger.error("demo_blockchain_db.csv not found. Please run the generator script.")
        return NO_MATCH, False
    except Exception as e:
        logger.error(f"Error reading CSV: {e}")

    logger.info("No matching transactions found in CSV.")
    return NO_MATCH, False


def format_demo_chain_hit_message(chat_title: str, filtered_text: str, params: dict, blockchain_line: str) -> str:
    """Fixed hackathon/demo copy for Telegram when L3 did not emit SEND_TELEGRAM_ALERT (edit as needed)."""
    snippet = (filtered_text or "").strip()[:800]
    return (
        "SENTINEL — HIGH-SIGNAL (demo, L3 verification did not fire)\n\n"
        f"Source: {chat_title}\n\n"
        "The analyzer requested an on-chain lookup; the offline dataset returned a matching row.\n\n"
        f"Search params: {params}\n\n"
        f"Chain result: {blockchain_line}\n\n"
        f"Post excerpt:\n{snippet}\n\n"
        "_Service notice: the verifier did not return SEND_TELEGRAM_ALERT; this is an offline CSV hit for the demo._"
    )

def enrich_alert_with_bounties(original_text: str) -> str:
    return ""

# ==========================================
# 2. ML PIPELINE
# ==========================================
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

def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def run_ml_pipeline_sync(raw_text: str, models_dict: dict) -> dict:
    """Returns verified/summary or a heuristic payload for the demo Telegram path."""
    filtered_text = clean_input_text(raw_text)
    
    tagger_model = models_dict['tagger_model']
    tokenizer_1 = models_dict['tokenizer_1']
    analyzer_model = models_dict['analyzer_model']
    tokenizer_2 = models_dict['tokenizer_2']

    # Stage 1: L1 Tagger
    logger.info("[STAGE 1] Running L1 (1.5B)...")
    instruction_1 = "Clean text, remove spam, extract tags."
    tagger_output = generate_response(tagger_model, tokenizer_1, instruction_1, f"Content: {filtered_text}")
    
    if "DROP_NOISE" in tagger_output:
        logger.info("L1: DROP_NOISE. Discarded.")
        return {"verified": False, "summary": None, "heuristic": None}

    # Stage 2: L2 Analyzer (First Pass)
    logger.info("[STAGE 2] Running L2 (3B) for strategy analysis...")
    instruction_2 = "Analyze content and determine strategy."
    analyzer_output_1 = generate_response(analyzer_model, tokenizer_2, instruction_2, tagger_output)
    
    strategy_json = extract_json(analyzer_output_1)
    
    if not strategy_json:
        return {"verified": False, "summary": None, "heuristic": None}

    action = strategy_json.get("action")
    
    if action in ["DROP_CONTEXT", "REQUEST_CONTEXT"]:
        logger.info(f"L2: {action}. No threat detected or missing data.")
        return {"verified": False, "summary": None, "heuristic": None}

    elif action == "SEARCH_BLOCKCHAIN":
        params = strategy_json.get("params", {})
        logger.info(f"L2 requested blockchain search with params: {params}")
        
        blockchain_result, chain_csv_hit = python_blockchain_search(params)
        
        # Stage 3: L2 Analyzer (Verification)
        instruction_3 = "Verify blockchain data against the reported event."
        input_3 = f"Content: {filtered_text}\nBlockchain: {blockchain_result}"
        
        logger.info("[STAGE 3] L2 verifying found transactions...")
        analyzer_output_2 = generate_response(analyzer_model, tokenizer_2, instruction_3, input_3)
        
        verification_json = extract_json(analyzer_output_2)

        if verification_json and verification_json.get("action") == "SEND_TELEGRAM_ALERT":
            return {
                "verified": True,
                "summary": verification_json.get("summary", "Confirmed threat found!"),
                "heuristic": None,
            }
        logger.info("L2: Blockchain data did not verify the threat (DROP_CONTEXT).")
        heuristic = None
        if chain_csv_hit:
            heuristic = {
                "filtered_text": filtered_text,
                "params": params,
                "blockchain_result": blockchain_result,
            }
        return {"verified": False, "summary": None, "heuristic": heuristic}

    elif action == "SEND_TELEGRAM_ALERT":
        return {
            "verified": True,
            "summary": strategy_json.get("summary", "Critical threat detected!"),
            "heuristic": None,
        }

    return {"verified": False, "summary": None, "heuristic": None}

# ==========================================
# 3. ASYNC WORKERS & STREAMERS
# ==========================================
async def _send_alert_silent(bot: Client, text: str) -> None:
    """Send without surfacing Telegram peer/API failures (invalid chat_id, bot blocked, etc.)."""
    try:
        await bot.send_message(chat_id=ALERT_CHAT_ID, text=text)
    except Exception:
        pass


async def ml_worker(bot: Client, queue: asyncio.Queue, models_dict: dict):
    """Worker that processes items from the queue using ML pipeline."""
    while True:
        message_text, chat_title = await queue.get()
        logger.info(f"Started processing message from {chat_title}")
        
        try:
            outcome = await asyncio.to_thread(run_ml_pipeline_sync, message_text, models_dict)
            verified = outcome.get("verified")
            summary = outcome.get("summary")
            heuristic = outcome.get("heuristic")

            if verified:
                logger.info("ALERT: Verified! ML finished. Triggering Telegram alert...")
                extra_onchain_data = await asyncio.to_thread(enrich_alert_with_bounties, message_text)
                alert_msg = (
                    f"SENTINEL VERIFIED ALERT\n\n"
                    f"Source: {chat_title}\n\n"
                    f"Analyzer Conclusion:\n{summary}{extra_onchain_data}"
                )

                if ALERT_CHAT_ID:
                    await _send_alert_silent(bot, alert_msg)
            elif (
                NOTIFY_ON_OFFLINE_CHAIN_MATCH
                and heuristic
                and ALERT_CHAT_ID
            ):
                logger.info("DEMO TG: offline CSV matched after SEARCH_BLOCKCHAIN but L3 dropped — sending service message.")
                demo_msg = await asyncio.to_thread(
                    format_demo_chain_hit_message,
                    chat_title,
                    heuristic["filtered_text"],
                    heuristic["params"],
                    heuristic["blockchain_result"],
                )
                await _send_alert_silent(bot, demo_msg)
        except Exception as e:
            logger.error(f"ML pipeline error: {str(e)}")
        finally:
            queue.task_done()

async def mock_post_streamer(queue: asyncio.Queue):
    """Infinite loop reading from CSV and sending to queue."""
    while True:
        try:
            with open("demo_tweets_stream.csv", mode="r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                
                for row in reader:
                    text = row.get("text", "")
                    if not text:
                        continue
                        
                    chat_title = "Deterministic Stream (Demo)"
                    logger.info("New post detected in stream. Added to queue.")
                    await queue.put((text, chat_title))
                    
                    delay = random.uniform(5.0, 15.0)
                    await asyncio.sleep(delay)
                    
        except FileNotFoundError:
            logger.error("demo_tweets_stream.csv not found! Waiting 10s...")
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"Streamer error: {e}")
            await asyncio.sleep(5)

# ==========================================
# 4. MAIN ENTRY POINT
# ==========================================
async def main():
    logger.info("Initializing Models into memory. Please wait...")
    
    # Load models ONCE here to prevent reloading and HTTP spam
    tokenizer_1 = AutoTokenizer.from_pretrained(TAGGER_BASE, local_files_only=False)
    base_model_1 = AutoModelForCausalLM.from_pretrained(TAGGER_BASE, device_map=DEVICE, dtype=torch.float16, local_files_only=False)
    tagger_model = PeftModel.from_pretrained(base_model_1, TAGGER_LORA)

    tokenizer_2 = AutoTokenizer.from_pretrained(ANALYZER_BASE, local_files_only=False)
    base_model_2 = AutoModelForCausalLM.from_pretrained(ANALYZER_BASE, device_map=DEVICE, dtype=torch.float16, local_files_only=False)
    analyzer_model = PeftModel.from_pretrained(base_model_2, ANALYZER_LORA)
    
    logger.info("Models loaded successfully.")

    models_dict = {
        'tagger_model': tagger_model,
        'tokenizer_1': tokenizer_1,
        'analyzer_model': analyzer_model,
        'tokenizer_2': tokenizer_2
    }

    logger.info("Starting Sentinel Console Agent...")
    
    notifier_bot = Client("notifier_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    ml_processing_queue = asyncio.Queue()

    await notifier_bot.start()
    logger.info("Telegram bot successfully authenticated and started.")
    
    worker_task = asyncio.create_task(ml_worker(notifier_bot, ml_processing_queue, models_dict))
    streamer_task = asyncio.create_task(mock_post_streamer(ml_processing_queue))
    
    try:
        await asyncio.gather(worker_task, streamer_task)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled. Shutting down...")
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}")
    finally:
        await notifier_bot.stop()
        logger.info("Agent stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n")
        logger.info("Process interrupted by user (Ctrl+C). Exiting.")