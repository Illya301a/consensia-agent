import pandas as pd

FILE_BLOCKCHAIN = 'transactions.csv'
OUTPUT_BLOCKCHAIN = 'filtered_transactions.csv'

# Minimum transaction amounts to be considered a 'whale'
THRESHOLDS = {
    'BTC': 5.0, 
    'ETH': 10.0
}

def read_csv_safe(filepath):
    """Attempt to read CSV with different encodings if the default fails."""
    try:
        return pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8', on_bad_lines='skip')
    except Exception:
        return pd.read_csv(filepath, sep=None, engine='python', encoding='latin1', on_bad_lines='skip')

def filter_blockchain_data():
    print("Starting blockchain data filtering...")
    
    df = read_csv_safe(FILE_BLOCKCHAIN)
    if df is None or df.empty:
        print("Error: Input file is empty or could not be read.")
        return

    initial_count = len(df)

    def is_whale(row):
        # Default threshold is 5.0 if currency is not in THRESHOLDS
        currency = str(row.get('Currency', '')).upper()
        amount = row.get('Amount', 0)
        threshold = THRESHOLDS.get(currency, 5.0)
        return amount >= threshold

    # Filter by whale thresholds and transaction status
    df = df[df.apply(is_whale, axis=1)]

    if 'Transaction_Status' in df.columns:
        df = df[df['Transaction_Status'] == 'Confirmed']

    # Remove duplicate transactions to ensure data integrity
    if 'Transaction_ID' in df.columns:
        df = df.drop_duplicates(subset=['Transaction_ID'])

    print("Filtering complete.")
    print(f"Statistics: Initial count: {initial_count} | Filtered count: {len(df)}")
    
    if not df.empty:
        df.to_csv(OUTPUT_BLOCKCHAIN, index=False)
        print(f"Results saved to: {OUTPUT_BLOCKCHAIN}")
        
        # Display sample for verification
        if 'Amount' in df.columns and 'Currency' in df.columns:
            print("Sample data after filtering:")
            print(df[['Amount', 'Currency']].head())
    else:
        print("Warning: Resulting dataset is empty. Consider lowering the THRESHOLDS.")

if __name__ == "__main__":
    filter_blockchain_data()