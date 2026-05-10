import json
import re
import os

# Configuration
INPUT_FILE = 'dataset_1_5B_tagger.jsonl'
OUTPUT_FILE = 'dataset_1_5B_tagger_CLEAN.jsonl'
MAX_DUPLICATES = 2

def normalize_text(text):
    """
    Normalizes text for fingerprinting to identify near-duplicates.
    """
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:60]

def clean_dataset():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print(f"Starting dataset cleaning: {INPUT_FILE}")

    seen_counts = {}
    removed_count = 0
    total_count = 0
    kept_count = 0

    with open(INPUT_FILE, 'r', encoding='utf-8') as f_in, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            total_count += 1
            try:
                data = json.loads(line.strip())
                raw_input = data.get("input", "")
                
                # Generate a short fingerprint to track occurrences
                fingerprint = normalize_text(raw_input)

                current_count = seen_counts.get(fingerprint, 0)
                if current_count < MAX_DUPLICATES:
                    seen_counts[fingerprint] = current_count + 1
                    f_out.write(line)
                    kept_count += 1
                else:
                    removed_count += 1
                    
            except json.JSONDecodeError:
                print(f"Skipping malformed JSON at line {total_count}")
                removed_count += 1

    print("-" * 30)
    print("Processing complete.")
    print(f"Total lines processed: {total_count}")
    print(f"Duplicates/corrupted removed: {removed_count}")
    print(f"Clean records saved: {kept_count}")
    print(f"Output saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    clean_dataset()