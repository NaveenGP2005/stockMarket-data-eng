import os
import time
import json
import requests
import boto3
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_KEY = os.getenv("FINNHUB_API_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

BASE_URL = "https://finnhub.io/api/v1/quote"
SYMBOLS = ["AAPL", "MSFT", "TSLA", "GOOGL", "AMZN"]

# Initialize S3 Client
s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

def fetch_quote(symbol):
    url = f"{BASE_URL}?symbol={symbol}&token={API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Check if the API returned valid data (Finnhub returns c=0 or empty if key/symbol is invalid)
        if not data or data.get("c") == 0:
            print(f"Warning: Finnhub returned empty data for {symbol}. Check your API Key.")
            return None
            
        data["symbol"] = symbol
        data["fetched_at"] = int(time.time())
        return data
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def main():
    print(f"Starting stock data producer uploading to S3 bucket: {S3_BUCKET}...")
    print("Press Ctrl+C to stop.")
    
    while True:
        bundle = []
        for symbol in SYMBOLS:
            quote = fetch_quote(symbol)
            if quote:
                bundle.append(quote)
                
        if bundle:
            # Generate folder structure based on current date
            now = datetime.utcnow()
            date_partition = now.strftime("year=%Y/month=%m/day=%d")
            timestamp = int(time.time())
            s3_key = f"raw/{date_partition}/quotes_{timestamp}.json"
            
            try:
                # Upload the bundle as a single JSON file to S3
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=json.dumps(bundle),
                    ContentType="application/json"
                )
                print(f"[{now.strftime('%H:%M:%S')}] Saved {len(bundle)} quotes -> s3://{S3_BUCKET}/{s3_key}")
            except Exception as e:
                print(f"Failed to upload to S3: {e}")
                
        # Wait 15 seconds before the next poll
        time.sleep(15)

if __name__ == "__main__":
    main()
