import os
import logging
from dotenv import load_dotenv
from notion_client import Client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NotionDebug")

def check_connection():
    load_dotenv()
    
    api_key = os.getenv("NOTION_API_KEY")
    target_db_id = os.getenv("NOTION_FINANCE_DATABASE_ID")

    if not api_key:
        logger.error("❌ NOTION_API_KEY is missing from .env")
        return

    logger.info(f"🔑 Testing with Token starting with: {api_key[:10]}...")
    logger.info(f"🎯 Looking for Finance DB ID: {target_db_id}")

    client = Client(auth=api_key)

    try:
        # 1. Who am I?
        me = client.users.me()
        logger.info(f"🤖 Bot Name: {me.get('name')} | Bot ID: {me.get('id')}")

        # 2. Search for everything I can see
        logger.info("🔍 Searching for all accessible Databases...")
        results = client.search(filter={"property": "object", "value": "database"}).get("results")
        
        found = False
        print("\n=== ACCESSIBLE DATABASES ===")
        for db in results:
            db_id = db["id"].replace("-", "")
            target_clean = target_db_id.replace("-", "") if target_db_id else ""
            
            title_list = db.get("title", [])
            title = title_list[0]["plain_text"] if title_list else "Untitled"
            
            match_mark = "✅ MATCH!" if db_id == target_clean else ""
            print(f"ID: {db['id']} | Name: {title} {match_mark}")
            
            if db_id == target_clean:
                found = True

        print("============================\n")

        if found:
            logger.info("✅ SUCCESS: The API can see the database. The issue is likely in your code logic or library version.")
        else:
            logger.error("❌ FAILURE: The API CANNOT see the database with this ID.")
            logger.error("👉 Solution: Go to the database page in Notion > ... > Connections > Add your integration again.")

    except Exception as e:
        logger.error(f"🔥 API Connection Failed: {e}")

if __name__ == "__main__":
    check_connection()