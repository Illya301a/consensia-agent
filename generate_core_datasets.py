import json
import requests
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AZURE_API_KEY")
ENDPOINT = os.getenv("AZURE_ENDPOINT")
MAX_WORKERS = 10

INPUT_FILE = 'refined_agent_data.jsonl'
OUT_TAGGER = 'dataset_1_5B_tagger.jsonl'
OUT_ANALYZER = 'dataset_3B_analyzer.jsonl'

ALLOWED_TAGS = [
    "hack", "exploit", "scam", "rug_pull", "security_breach",
    "whale_alert", "large_transfer", "exchange_flow",
    "listing", "delisting", "partnership", "integration",
    "mainnet", "hardfork", "upgrade", "migration",
    "token_unlock", "airdrop", "vesting", "burn",
    "regulation", "lawsuit", "compliance", "sec",
    "defi", "nft", "web3", "smart_contract",
    "bitcoin", "ethereum", "solana", "stablecoin"
]

def clean_raw_text(text):
    """Basic text cleaning: removes URLs, mentions, and extra whitespace."""
    text = re.sub(r'\\n|\n', ' ', text)
    text = re.sub(r'https?:\/\/\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def ask_azure_llm(raw_text, tx_data):
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY
    }
    tags_str = ", ".join(ALLOWED_TAGS)
    
    system_prompt = f"""You are a Web3 AI data annotation expert building training datasets for an autonomous agent.
You will receive a raw social media post and blockchain transaction data.

CRITICAL RULE 1: For the "tags" array, use ONLY tags from this list: [{tags_str}]
CRITICAL RULE 2: You must evaluate the priority ("HIGH" or "LOW") and determine the correct action.
CRITICAL RULE 3: If any specific blockchain network or cryptocurrency is mentioned or clearly implied in the text, you MUST include its exact corresponding tag from the Allowed Tags list.

Return a strict JSON object:
{{
  "is_noise": boolean,
  "cleaned_text": "Extract only the core meaning, fix grammar, remove any remaining junk",
  "tags": ["tag1", "tag2"],
  "priority": "HIGH" | "LOW",
  "thought": "Internal monologue explaining the reasoning for the chosen action",
  "action": "SEARCH_BLOCKCHAIN" | "DROP_CONTEXT" | "REQUEST_CONTEXT",
  "context_needed": "If action is REQUEST_CONTEXT, describe what missing info is needed",
  "telegram_summary": "A Telegram bot alert based on findings (only if action is SEARCH_BLOCKCHAIN). Else null."
}}"""

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Post: {raw_text}\nBlockchain Event: {tx_data}"}
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }

    # Exponential backoff for API rate limiting
    for attempt in range(5):
        try:
            response = requests.post(ENDPOINT, headers=headers, json=payload)
            if response.status_code == 429: 
                wait_time = 2 ** attempt 
                print(f"Rate limit hit. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            result = response.json()
            return json.loads(result['choices'][0]['message']['content'])
        
        except Exception as e:
            print(f"Error: {e}. Attempt {attempt+1}/5...")
            time.sleep(2)
            
    return None 

def process_single_row(line_data):
    """Processes a single dataset row and returns formatted entries for Tagger and Analyzer."""
    data = json.loads(line_data)
    raw_feed = data['instruction'].replace("Autonomous Agent Mode. Input: ", "")
    tx_data = data.get('input', 'No blockchain data')
    
    clean_feed = clean_raw_text(raw_feed)
    llm_response = ask_azure_llm(clean_feed, tx_data)
    
    if not llm_response:
        return None, None 
        
    tagger_entries = []
    analyzer_entries = []

    # Format Tagger Dataset Output
    if llm_response.get("is_noise"):
        tagger_entries.append({
            "instruction": "Filter and tag incoming stream.",
            "input": clean_feed,
            "output": json.dumps({"action": "DROP_NOISE"})
        })
    else:
        safe_tags = [t for t in llm_response.get("tags", []) if t in ALLOWED_TAGS]
        tagger_entries.append({
            "instruction": "Filter and tag incoming stream.",
            "input": clean_feed,
            "output": json.dumps({
                "action": "PROCESS_FORWARD",
                "clean_text": llm_response.get("cleaned_text"),
                "tags": safe_tags
            }, ensure_ascii=False)
        })

    # Format Analyzer Dataset Output
    if not llm_response.get("is_noise"):
        clean_text = llm_response.get("cleaned_text")
        safe_tags = [t for t in llm_response.get("tags", []) if t in ALLOWED_TAGS]
        
        decision_output = {
            "thought": llm_response.get("thought", ""),
            "priority": llm_response.get("priority", "LOW"),
            "action": llm_response.get("action", "DROP_CONTEXT")
        }
        
        if decision_output["action"] == "REQUEST_CONTEXT":
            decision_output["context_needed"] = llm_response.get("context_needed")

        analyzer_entries.append({
            "instruction": "Analyze content and determine strategy.",
            "input": f"Content: {clean_text}\nTags: {safe_tags}",
            "output": json.dumps(decision_output, ensure_ascii=False)
        })
        
        if decision_output["action"] == "SEARCH_BLOCKCHAIN" and "No direct large-scale movements" not in tx_data:
            analyzer_entries.append({
                "instruction": "Generate final alert based on findings.",
                "input": f"Content: {clean_text}\nBlockchain: {tx_data}",
                "output": json.dumps({
                    "action": "SEND_TELEGRAM_ALERT",
                    "summary": llm_response.get("telegram_summary")
                }, ensure_ascii=False)
            })

    return tagger_entries, analyzer_entries

def generate_datasets():
    print(f"Starting dataset generation with {MAX_WORKERS} workers...")
    
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    limit = len(lines)
    start_index = 0
    count_tagger = 0
    count_analyzer = 0

    # Resume capability: check existing files for progress
    if os.path.exists(OUT_TAGGER):
        with open(OUT_TAGGER, 'r', encoding='utf-8') as f:
            start_index = sum(1 for _ in f)
        count_tagger = start_index

    if os.path.exists(OUT_ANALYZER):
        with open(OUT_ANALYZER, 'r', encoding='utf-8') as f:
            count_analyzer = sum(1 for _ in f)

    if start_index > 0:
        print(f"Resuming from line {start_index}...")
    
    mode = 'a' if start_index > 0 else 'w'
    lines_to_process = lines[start_index:limit]

    with open(OUT_TAGGER, mode, encoding='utf-8') as f_tagger, \
         open(OUT_ANALYZER, mode, encoding='utf-8') as f_analyzer:

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for i, result in enumerate(executor.map(process_single_row, lines_to_process)):
                current_idx = start_index + i + 1
                
                if result == (None, None):
                    print(f"[{current_idx}/{limit}] Warning: API error, skipping row.")
                    continue
                
                tagger_res, analyzer_res = result
                
                for te in tagger_res:
                    f_tagger.write(json.dumps(te, ensure_ascii=False) + '\n')
                    count_tagger += 1
                
                for ae in analyzer_res:
                    f_analyzer.write(json.dumps(ae, ensure_ascii=False) + '\n')
                    count_analyzer += 1
                
                f_tagger.flush()
                f_analyzer.flush()
                
                if current_idx % 10 == 0:
                    print(f"[{current_idx}/{limit}] Processed successfully.")

    # Add synthetic data for skill fine-tuning
    print("Appending synthetic skill-data...")
    synthetic_requests = [
        {
            "instruction": "Convert missing context description into DB search tags.",
            "input": "Need to verify if there are any recent hacks related to the Ronin bridge.",
            "output": json.dumps({"action": "SEARCH_DB", "tags": ["hack", "security_breach"]})
        },
        {
            "instruction": "Convert missing context description into DB search tags.",
            "input": "Looking for large whale transfers of Solana over the last 24 hours.",
            "output": json.dumps({"action": "SEARCH_DB", "tags": ["solana", "whale_alert", "large_transfer"]})
        }
    ]
    
    for req in synthetic_requests:
        f_tagger.write(json.dumps(req, ensure_ascii=False) + '\n')
        count_tagger += 1

    print("\nGeneration complete.")
    print(f"Tagger (1.5B): {count_tagger} samples")
    print(f"Analyzer (3B): {count_analyzer} samples")

if __name__ == "__main__":
    generate_datasets()