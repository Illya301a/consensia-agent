import pandas as pd
import json
import random

# Configuration
FILES_TWEETS = ['tweets_format_1.csv', 'tweets_format_2.csv']
OUTPUT_FILE = 'final_training_dataset.jsonl'

# Keywords used to classify high-signal crypto events
CRYPTO_KEYWORDS = [
    'hack', 'exploit', 'moving', 'liquidating', 'unlocked', 'vesting',
    'burn', 'halving', 'mainnet', 'upgrade', 'hardfork', 'migration',
    'partnership', 'integration', 'listed', 'binance', 'coinbase',
    'funding', 'raised', 'treasury', 'accumulation', 'airdrop', 'snapshot'
]

def read_csv_safe(filepath):
    """Attempt to read CSV with multiple encodings to handle diverse data sources."""
    try:
        return pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8', on_bad_lines='skip')
    except Exception:
        return pd.read_csv(filepath, sep=None, engine='python', encoding='latin1', on_bad_lines='skip')

def normalize_df(df):
    """Extract and normalize text content from various possible CSV column names."""
    if df.empty: 
        return df
    
    cols = df.columns.tolist()
    new_df = pd.DataFrame()
    
    # Common naming conventions for tweet/post content
    text_match = [c for c in cols if c.lower() in ['content', 'text', 'actual raw content/post', 'body']]
    
    if text_match:
        new_df['text'] = df[text_match[0]]
        return new_df
    return pd.DataFrame()

def process_and_label():
    print(f"Starting data collection from {len(FILES_TWEETS)} sources...")
    all_text = []
    
    for f in FILES_TWEETS:
        raw_df = read_csv_safe(f)
        norm_df = normalize_df(raw_df)
        if not norm_df.empty:
            all_text.extend(norm_df['text'].dropna().astype(str).tolist())

    print(f"Total raw records collected: {len(all_text)}")

    final_dataset = []
    print("Generating labels (Action & DROP logic)...")
    
    for text in all_text:
        # Simple keyword-based filtering for initial dataset labeling
        has_keyword = any(kw.lower() in text.lower() for kw in CRYPTO_KEYWORDS)
        
        if has_keyword:
            entry = {
                "instruction": f"Analyze the following crypto feed: {text}",
                "output": {
                    "action": "KEEP_AND_ANALYZE",
                    "tag": "CRYPTO_EVENT",
                    "reason": "Post contains market-moving keywords."
                }
            }
        else:
            entry = {
                "instruction": f"Analyze the following crypto feed: {text}",
                "output": {
                    "action": "DROP",
                    "tag": "NOISE",
                    "reason": "Irrelevant information, clearing context window."
                }
            }
        
        final_dataset.append(entry)

    # Shuffle to ensure balanced distribution during training
    random.shuffle(final_dataset)

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for item in final_dataset:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        print(f"Success: Created {len(final_dataset)} training examples.")
        print(f"Output saved to: {OUTPUT_FILE}")
    except IOError as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    process_and_label()