import csv
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'dashboard'))
from sync_index import fetch_all_articles

def main():
    print("Fetching articles with proper extracted titles from sitemap...")
    articles = fetch_all_articles()
    
    csv_path = 'shanethegamer_articles_updated.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['url', 'title', 'category', 'lastmod'])
        writer.writeheader()
        writer.writerows(articles)
        
    print(f"Success! Updated {csv_path} with {len(articles)} articles containing real meta titles.")

if __name__ == "__main__":
    main()
