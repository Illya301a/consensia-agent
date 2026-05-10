import json
import requests
import time
import os
import random
import csv
import re
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration
API_KEY = os.getenv("AZURE_API_KEY")
ENDPOINT = os.getenv("AZURE_ENDPOINT")
MAX_WORKERS = 10

INPUT_DATASET = os.path.join(BASE_DIR, 'dataset_3B_analyzer.jsonl')
OUTPUT_DATASET = os.path.join(BASE_DIR, 'dataset_3B_analyzer_V2.jsonl')
TRANSACTIONS_CSV = os.path.join(BASE_DIR, 'filtered_transactions.csv')

def load_fake_txs():
    """Loads transaction data from CSV to use as negative samples for dataset augmentation."""
    fake_txs = []
    headers = ["Transaction_ID", "Sender_Address", "Receiver_Address", "Amount", "Fee", "Date", "Block", "Miner", "Asset", "Type", "Status", "Extra"]
    
    if os.path.exists(TRANSACTIONS_CSV):
        try:
            with open(TRANSACTIONS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                csv_headers = next(reader, None)
                if csv_headers:
                    headers = csv_headers
                
                for row in reader:
                    if row:  
                        formatted_row = ", ".join([f"{h}: {v}" for h, v in zip(headers, row)])
                        
                        tx_id = row[0] if len(row) > 0 else "UNKNOWN"
                        amount = row[3] if len(row) > 3 else "0"
                        asset = row[8] if len(row) > 8 else "UNKNOWN"
                        
                        fake_txs.append({
                            "id": tx_id,
                            "amount": amount,
                            "asset": asset,
                            "text": formatted_row
                        })
            print(f"[INFO] Loaded {len(fake_txs)} transactions from CSV.")
        except Exception as e:
            print(f"[ERROR] Failed to read CSV: {e}")
            
    # Fallback if CSV is missing or empty
    if len(fake_txs) < 5:
        print("[WARN] Using fallback transaction list.")
        fake_txs = [
            {"id": "TX2QW62Q5XM17K", "amount": "11.39", "asset": "ETH", "text": "Transaction_ID: TX2QW62Q5XM17K, Sender_Address: 0xd37..., Receiver_Address: 0x4a3..., Amount: 11.39, Asset: ETH, Status: Confirmed"},
            {"id": "TXH9R37H4G92WK", "amount": "8.92", "asset": "BTC", "text": "Transaction_ID: TXH9R37H4G92WK, Sender_Address: 0x65f..., Receiver_Address: bc1q..., Amount: 8.92, Asset: BTC, Status: Confirmed"}
        ]
    return fake_txs

FAKE_TXS_LIST = load_fake_txs()

def generate_search_params(content, tags):
    """Calls LLM to generate structured search parameters from raw news content."""
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY
    }
    
    prompt = """You are an autonomous Web3 AI agent. Based on the news post and tags, generate the exact search parameters needed to query the blockchain database.

CRITICAL RULES:
1. "network" MUST NOT be null if the Tags contain hints (e.g., 'ethereum', 'bitcoin', 'solana', 'bsc'). You must infer it.
2. "asset" MUST NOT be null if it can be inferred from context (e.g., 'ETH', 'BTC', 'USDC').
3. "min_amount" should be >0 if the news implies a significant hack, exploit, or whale transfer.

Return ONLY a valid JSON object.

{
  "network": "ethereum" | "bitcoin" | "solana" | "bsc",
  "min_amount": 1000, 
  "asset": "ETH" | "BTC" | "USDC" | "SOL",
  "time_window": "last_24_hours" | "last_7_days",
  "keywords": ["bridge", "hack", "exploit"] 
}"""

    payload = {
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Content: {content}\nTags: {tags}"}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    for attempt in range(3):
        try:
            res = requests.post(ENDPOINT, headers=headers, json=payload, timeout=10)
            if res.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            res.raise_for_status()
            return json.loads(res.json()['choices'][0]['message']['content'])
        except Exception:
            time.sleep(1)
    
    return {"network": "ethereum", "min_amount": 0, "asset": "ETH", "time_window": "last_24_hours", "keywords": []}

def format_success_tx(blockchain_text):
    """Utility to format matching transactions into a standardized string."""
    match = re.search(r'([0-9\.]+)\s*([a-zA-Z]+)\s*move', blockchain_text, re.IGNORECASE)
    if match:
        amount = match.group(1)
        asset = match.group(2).upper()
        return f"Transaction_ID: TX_ALERT_{random.randint(1000,9999)}, Sender_Address: 0x_unknown, Receiver_Address: 0x_unknown, Amount: {amount}, Asset: {asset}, Status: Confirmed"
    return blockchain_text 

def process_group(group):
    """Processes logic blocks to generate multi-step reasoning for the dataset."""
    new_entries = []
    
    if group["type"] == "other":
        new_entries.append(group["data"])
        return new_entries

    if group["type"] == "search":
        decision_data = group["decision"]
        alert_data = group["alert"] 
        
        output_obj = json.loads(decision_data["output"])
        input_text = decision_data["input"]
        content_only = input_text.split("\nTags:")[0].replace("Content: ", "").strip()
        
        # 1. Update initial decision with LLM-generated search params
        params = generate_search_params(input_text, output_obj.get("tags", []))
        output_obj["params"] = params
        
        new_entries.append({
            "instruction": decision_data["instruction"],
            "input": input_text,
            "output": json.dumps(output_obj, ensure_ascii=False)
        })

        # 2. Augment with 'Negative' samples (noise reduction training)
        if alert_data:
            num_fakes = random.randint(1, 2)
            fake_samples = random.sample(FAKE_TXS_LIST, num_fakes)
            
            for fake_tx in fake_samples:
                dynamic_thought = f"Analyzed transaction {fake_tx['id']}. The transaction involves {fake_tx['amount']} {fake_tx['asset']}. These parameters do not align with the scale, asset, or network expected from the reported event. Skipping as irrelevant noise."
                
                new_entries.append({
                    "instruction": "Verify blockchain data against the reported event.",
                    "input": f"Content: {content_only}\nBlockchain: {fake_tx['text']}",
                    "output": json.dumps({
                        "action": "DROP_CONTEXT",
                        "thought": dynamic_thought
                    }, ensure_ascii=False)
                })

            # 3. Handle 'Empty result' scenario
            if random.random() < 0.3:
                new_entries.append({
                    "instruction": "Verify blockchain data against the reported event.",
                    "input": f"Content: {content_only}\nBlockchain: No matching transactions found.",
                    "output": json.dumps({
                        "action": "DROP_CONTEXT",
                        "thought": "The database search returned no matching transactions based on the generated parameters. The reported event cannot be verified on-chain. Dropping context."
                    }, ensure_ascii=False)
                })

            # 4. Final successful verification step
            old_alert_input = alert_data["input"]
            blockchain_part = old_alert_input.split("Blockchain: ")[-1].strip()
            formatted_success_tx_str = format_success_tx(blockchain_part)
            
            new_entries.append({
                "instruction": "Verify blockchain data against the reported event.",
                "input": f"Content: {content_only}\nBlockchain: {formatted_success_tx_str}",
                "output": alert_data["output"]
            })

    return new_entries

def main():
    if not os.path.exists(INPUT_DATASET):
        print(f"[ERROR] Input file {INPUT_DATASET} not found.")
        return

    print("[PROCESS] Grouping original dataset entries...")
    with open(INPUT_DATASET, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    grouped_data = []
    i = 0
    while i < len(lines):
        try:
            line_content = lines[i].strip()
            if not line_content:
                i += 1
                continue
            item = json.loads(line_content)
        except Exception as e:
            i += 1
            continue

        # Logic for grouping SEARCH decisions with their corresponding ALERT outputs
        if item.get("instruction") == "Analyze content and determine strategy.":
            out_json = json.loads(item["output"])
            if out_json.get("action") == "SEARCH_BLOCKCHAIN":
                next_item = None
                if i + 1 < len(lines):
                    try:
                        potential_next = json.loads(lines[i+1].strip())
                        if potential_next.get("instruction") == "Generate final alert based on findings.":
                            next_item = potential_next
                            i += 1 
                    except:
                        pass
                
                grouped_data.append({"type": "search", "decision": item, "alert": next_item})
            else:
                grouped_data.append({"type": "other", "data": item})
        elif item.get("instruction") == "Generate final alert based on findings.":
             item["instruction"] = "Verify blockchain data against the reported event."
             grouped_data.append({"type": "other", "data": item})
        else:
            grouped_data.append({"type": "other", "data": item})
        i += 1

    print(f"[INFO] Found {len(grouped_data)} logic blocks. Starting augmentation...")

    processed_count = 0
    added_count = 0

    with open(OUTPUT_DATASET, 'w', encoding='utf-8') as f_out:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for new_rows in executor.map(process_group, grouped_data):
                processed_count += 1
                if not new_rows:
                    continue
                
                for row in new_rows:
                    f_out.write(json.dumps(row, ensure_ascii=False) + '\n')
                    added_count += 1
                
                if processed_count % 100 == 0:
                    print(f"[PROGRESS] Blocks: {processed_count}/{len(grouped_data)} | Lines written: {added_count}")

    print(f"[SUCCESS] Dataset augmentation complete.")
    print(f"[INFO] Output file: {OUTPUT_DATASET} ({added_count} total lines)")

if __name__ == "__main__":
    main()