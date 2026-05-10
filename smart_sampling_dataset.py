import json
import random

# Configuration for dataset balancing
INPUT_FILE = 'final_training_dataset.jsonl'
OUTPUT_FILE = 'smart_compact_dataset.jsonl'
TARGET_SIZE = 20000

# Filtering criteria
BLACKLIST = ['giveaway', 'contest', 'win', 'prize', 'gift', 'shibadoge', 'sugar mommy', 'essay']
HIGH_PRIORITY = ['hack', 'exploit', 'stolen', 'liquidating', 'unlocked', 'vesting', 'migration', 'mainnet']
NORMAL_PRIORITY = ['bitcoin', 'ethereum', 'btc', 'eth', 'binance', 'coinbase', 'funding', 'partnership']

def get_score(text):
    """Assigns a priority score based on keyword matching."""
    text = text.lower()
    if any(word in text for word in BLACKLIST):
        return 0
    
    score = 0
    for word in HIGH_PRIORITY:
        if word in text: 
            score += 5
    for word in NORMAL_PRIORITY:
        if word in text: 
            score += 1
    return score

def process_smart_sampling():
    important_pool = []
    noise_pool = []

    print("Starting smart filtration process...")

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
                
            data = json.loads(line)
            # Remove prompt prefix to analyze raw content
            text = data['instruction'].replace("Analyze the following crypto feed: ", "")
            
            score = get_score(text)
            
            # High-signal threshold: significant keywords + minimum length
            if score >= 5 and len(text) > 40:
                data['output']['action'] = "KEEP_AND_ANALYZE"
                data['output']['tag'] = "HIGH_SIGNAL"
                important_pool.append(data)
            else:
                data['output']['action'] = "DROP"
                data['output']['tag'] = "NOISE"
                noise_pool.append(data)

    print(f"High-signal entries found: {len(important_pool)}")
    print(f"Noise entries filtered: {len(noise_pool)}")

    final_list = important_pool
    remaining_slots = TARGET_SIZE - len(final_list)
    
    # Fill remaining capacity with random noise samples for model robustness
    if remaining_slots > 0 and noise_pool:
        sampled_noise = random.sample(noise_pool, min(remaining_slots, len(noise_pool)))
        final_list.extend(sampled_noise)

    random.shuffle(final_list)
    
    # Writing the final dataset (limited to TARGET_SIZE)
    output_count = 0
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for item in final_list[:TARGET_SIZE]:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            output_count += 1

    print(f"Process complete. Smart dataset saved with {output_count} rows.")

if __name__ == "__main__":
    process_smart_sampling()