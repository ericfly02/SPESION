import os
import sys
import logging
from notion_client import Client
from dotenv import load_dotenv

# Add src to path to import notion_mcp
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

def verify_fix():
    load_dotenv()
    
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        logger.error("NOTION_API_KEY not found in environment")
        return

    # Use the same DB ID as before
    db_id = "038079bc-8a1e-4092-b643-aa7c5db67cdc"
    
    logger.info(f"Attempting to query database using patched _query_notion_db: {db_id}")
    
    try:
        from src.tools.notion_mcp import _query_notion_db, _get_notion_client
        
        client = _get_notion_client()
        if not client:
             logger.error("Failed to get notion client from src.tools.notion_mcp")
             return

        # Try to query the database using the new implementation
        logger.info("Calling _query_notion_db...")
        result = _query_notion_db(client, db_id, page_size=1)
        
        logger.info("SUCCESS: _query_notion_db returned results!")
        logger.info(f"Results count: {len(result.get('results', []))}")
        
    except Exception as e:
        logger.error(f"FAILED: _query_notion_db error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_fix()
