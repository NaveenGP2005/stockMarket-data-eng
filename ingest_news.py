import os
import yfinance as yf
import chromadb
import ollama
import hashlib
from datetime import datetime

# Configure tickers to scrape news for
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "financial_news"

def get_hash_id(text: str) -> str:
    """Generate a unique ID based on article title to prevent duplicate insertions."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def get_ollama_embedding(text: str) -> list:
    """Generate embedding for the text using local Ollama nomic-embed-text model."""
    try:
        response = ollama.embeddings(model="nomic-embed-text", prompt=text)
        return response["embedding"]
    except Exception as e:
        print(f"Error generating embedding via Ollama: {e}")
        raise e

def main():
    print(f"[{datetime.now()}] Initializing ChromaDB at '{CHROMA_PATH}'...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    
    print(f"[{datetime.now()}] Fetching news from Yahoo Finance for tickers: {TICKERS}")
    
    total_added = 0
    for symbol in TICKERS:
        print(f"\nProcessing {symbol}...")
        try:
            ticker = yf.Ticker(symbol)
            news_list = ticker.news
            if not news_list:
                print(f"No news found for {symbol}.")
                continue
                
            print(f"Found {len(news_list)} articles for {symbol}. Ingesting...")
            
            for article in news_list:
                content = article.get("content", {})
                if not content:
                    continue
                
                title = content.get("title", "")
                summary = content.get("summary", "")
                
                # Parse URL
                canonical_url = content.get("canonicalUrl", {})
                link = canonical_url.get("url", "") if isinstance(canonical_url, dict) else ""
                
                # Parse provider
                provider = content.get("provider", {})
                publisher = provider.get("displayName", "") if isinstance(provider, dict) else ""
                
                # Parse publish date
                pub_date = content.get("pubDate", "")
                
                if not title:
                    continue
                
                # Create a unique ID using the link or title
                doc_id = get_hash_id(link or title)
                
                # Check if document already exists in ChromaDB to avoid duplicates
                existing = collection.get(ids=[doc_id])
                if existing and existing["ids"]:
                    print(f" - Article already exists, skipping: '{title[:50]}...'")
                    continue
                
                # Construct document text (include summary for better embeddings)
                doc_text = f"Title: {title}\nSummary: {summary}\nPublisher: {publisher}\nTicker: {symbol}\nPublished: {pub_date}"
                metadata = {
                    "symbol": symbol,
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "pub_date": pub_date
                }
                
                # Generate embedding locally
                embedding = get_ollama_embedding(doc_text)
                
                # Add to collection
                collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[doc_text],
                    metadatas=[metadata]
                )
                total_added += 1
                print(f" - Successfully indexed: '{title[:50]}...'")
                
        except Exception as e:
            print(f"Error processing news for {symbol}: {e}")

    print(f"\n[{datetime.now()}] Ingestion complete. Total new articles indexed: {total_added}")
    print(f"Total documents in collection '{COLLECTION_NAME}': {collection.count()}")

if __name__ == "__main__":
    main()
