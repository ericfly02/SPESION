import os
import sys
import logging
from notion_client import Client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

def verify_notion_access():
    load_dotenv()
    
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        logger.error("NOTION_API_KEY not found in environment")
        return

    # Database ID from the user report / .env
    # The user mentioned this ID in the error logs: 038079bc-8a1e-4092-b643-aa7c5db67cdc
    db_id = "038079bc-8a1e-4092-b643-aa7c5db67cdc"
    
    logger.info(f"Attempting to access database: {db_id}")
    
    client = Client(auth=api_key)
    
    # 1. Try Retrieve
    logger.info("--- Test 1: client.databases.retrieve ---")
    try:
        db = client.databases.retrieve(database_id=db_id)
        logger.info("SUCCESS: Database retrieved via retrieve()")
        logger.info(f"Name: {db.get('title', [{}])[0].get('plain_text', 'Unknown')}")
    except Exception as e:
        logger.error(f"FAILED: retrieve() error: {e}")

    # 2. Try Query
    logger.info("\n--- Test 2: client.databases.query ---")
    try:
        results = client.databases.query(database_id=db_id, page_size=1)
        logger.info("SUCCESS: Database queried via query()")
        logger.info(f"Retrieved {len(results.get('results', []))} items")
    except Exception as e:
        logger.error(f"FAILED: query() error: {e}")

    # 3. Check for the misleading 'data_sources' (just to confirm it doesn't exist/work)
    logger.info("\n--- Test 3: client.data_sources.query (expecting failure) ---")
    if hasattr(client, "data_sources"):
        try:
            client.data_sources.query(data_source_id=db_id)
            logger.info("Wait, data_sources.query WORKED? That's unexpected.")
        except Exception as e:
             logger.info(f"As expected, data_sources failed: {e}")
    else:
        logger.info("client.data_sources does not exist in this SDK version.")

if __name__ == "__main__":
    verify_notion_access()
