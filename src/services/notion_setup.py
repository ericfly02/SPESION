"""Notion Setup Service - Initialization of the SPESION workspace."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

class NotionSetupService:
    """Service to initialize the Notion workspace structure."""

    def __init__(self, api_key: str):
        try:
            from notion_client import Client
            self.client = Client(auth=api_key)
        except ImportError:
            raise ImportError("notion-client not installed")

    def initialize_workspace(self) -> dict[str, str]:
        """Creates the full SPESION workspace structure.
        
        Returns:
            Dict of created database IDs.
        """
        logger.info("Initializing SPESION Workspace in Notion...")
        
        # 1. Create Root Page "SPESION HQ"
        root_page = self._create_root_page()
        root_id = root_page["id"]
        logger.info(f"Root page created: {root_id}")

        ids = {}

        # 2. Create Databases
        ids["knowledge"] = self._create_knowledge_db(root_id)
        ids["tasks"] = self._create_tasks_db(root_id)
        ids["crm"] = self._create_crm_db(root_id)
        ids["finance"] = self._create_finance_db(root_id)
        ids["goals"] = self._create_goals_db(root_id)

        # 3. Update .env file
        self._update_env_file(ids)
        
        return ids

    def _create_root_page(self) -> dict[str, Any]:
        """Creates the main dashboard page."""
        # Note: We cannot create a page at the absolute root via API easily 
        # without a parent page ID, unless we search for one or the user provides it.
        # However, we can search for a page named "SPESION HQ" to avoid duplicates,
        # or ask the user to share a page with the integration.
        
        # Strategy: Search for existing "SPESION HQ". If not found, we create one 
        # but the API requires a parent. 
        # Fallback: We'll create it as a child of the workspace root if possible 
        # (Notion API limits this). 
        # BEST PRACTICE: The integration acts as a user. We'll search for any page 
        # shared with the integration and create the HQ inside it, OR just search 
        # if "SPESION HQ" exists.
        
        search = self.client.search(query="SPESION HQ", filter={"property": "object", "value": "page"})
        if search["results"]:
            logger.info("Found existing SPESION HQ page.")
            return search["results"][0]
            
        # If not found, we need a parent. We'll search for ANY page shared with the bot
        # and use the first one as parent, or raise an error if none found.
        # Actually, let's try to find a top-level page.
        search_all = self.client.search(filter={"property": "object", "value": "page"})
        if not search_all["results"]:
            raise ValueError(
                "Error de Permisos Notion: No encuentro ninguna página compartida con la integración.\n"
                "SOLUCIÓN: Ve a Notion, abre una página, haz clic en '...' > 'Conexiones' "
                "y añade la conexión de tu integración (SPESION)."
            )
        
        parent_page = search_all["results"][0]
        
        return self.client.pages.create(
            parent={"type": "page_id", "page_id": parent_page["id"]},
            properties={
                "title": [{"text": {"content": "SPESION HQ"}}],
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"text": {"content": "SPESION Command Center"}}]}
                }
            ],
            icon={"type": "emoji", "emoji": "🧠"}
        )

    def _create_knowledge_db(self, parent_id: str) -> str:
        """Creates Knowledge/Journal DB."""
        db = self.client.databases.create(
            parent={"type": "page_id", "page_id": parent_id},
            title=[{"type": "text", "text": {"content": "🧠 Knowledge & Journal"}}],
            properties={
                "Name": {"title": {}},
                "Type": {
                    "select": {
                        "options": [
                            {"name": "Journal", "color": "blue"},
                            {"name": "Paper", "color": "red"},
                            {"name": "Note", "color": "gray"},
                            {"name": "Insight", "color": "yellow"},
                        ]
                    }
                },
                "Date": {"date": {}},
                "Tags": {"multi_select": {}},
                "Mood": {
                    "select": {
                        "options": [
                            {"name": "Great", "color": "green"},
                            {"name": "Good", "color": "blue"},
                            {"name": "Okay", "color": "gray"},
                            {"name": "Bad", "color": "orange"},
                            {"name": "Terrible", "color": "red"},
                        ]
                    }
                },
                "Energy": {"number": {"format": "number"}},
                "URL": {"url": {}},
                "ArXiv ID": {"rich_text": {}},
                "Authors": {"rich_text": {}},
                "Summary": {"rich_text": {}},
            }
        )
        return db["id"]

    def _create_tasks_db(self, parent_id: str) -> str:
        """Creates Tasks DB."""
        db = self.client.databases.create(
            parent={"type": "page_id", "page_id": parent_id},
            title=[{"type": "text", "text": {"content": "✅ Tasks & Projects"}}],
            properties={
                "Name": {"title": {}},
                "Status": {
                    "status": {
                        "options": [
                            {"name": "Todo", "color": "gray"},
                            {"name": "In Progress", "color": "blue"},
                            {"name": "Done", "color": "green"},
                        ]
                    }
                },
                "Priority": {
                    "select": {
                        "options": [
                            {"name": "High", "color": "red"},
                            {"name": "Medium", "color": "yellow"},
                            {"name": "Low", "color": "blue"},
                        ]
                    }
                },
                "Due Date": {"date": {}},
                "Project": {
                    "select": {
                        "options": [
                            {"name": "Civita", "color": "purple"},
                            {"name": "Creda", "color": "green"},
                            {"name": "WhoHub", "color": "orange"},
                            {"name": "Personal", "color": "gray"},
                            {"name": "NTTData", "color": "blue"},
                        ]
                    }
                },
                "Cognitive Load": {
                    "select": {
                        "options": [
                            {"name": "High (Deep Work)", "color": "red"},
                            {"name": "Medium", "color": "yellow"},
                            {"name": "Low (Admin)", "color": "blue"},
                        ]
                    }
                },
            }
        )
        return db["id"]

    def _create_crm_db(self, parent_id: str) -> str:
        """Creates Network/CRM DB."""
        db = self.client.databases.create(
            parent={"type": "page_id", "page_id": parent_id},
            title=[{"type": "text", "text": {"content": "🤝 Network (WhoHub)"}}],
            properties={
                "Name": {"title": {}},
                "Company": {"rich_text": {}},
                "Role": {"rich_text": {}},
                "Strength": {
                    "select": {
                        "options": [
                            {"name": "⭐⭐⭐⭐⭐ Inner Circle", "color": "green"},
                            {"name": "⭐⭐⭐⭐ Trusted", "color": "blue"},
                            {"name": "⭐⭐⭐ Active", "color": "yellow"},
                            {"name": "⭐⭐ Professional", "color": "gray"},
                            {"name": "⭐ Acquaintance", "color": "default"},
                        ]
                    }
                },
                "Last Contact": {"date": {}},
                "How Met": {"rich_text": {}},
                "Tags": {"multi_select": {}},
                "LinkedIn": {"url": {}},
            }
        )
        return db["id"]

    def _create_finance_db(self, parent_id: str) -> str:
        """Creates Finance Portfolio DB."""
        db = self.client.databases.create(
            parent={"type": "page_id", "page_id": parent_id},
            title=[{"type": "text", "text": {"content": "💰 Finance Portfolio"}}],
            properties={
                "Ticker": {"title": {}}, # Using Name as Ticker
                "Type": {
                    "select": {
                        "options": [
                            {"name": "ETF", "color": "blue"},
                            {"name": "Stock", "color": "green"},
                            {"name": "Crypto", "color": "orange"},
                            {"name": "Cash", "color": "gray"},
                        ]
                    }
                },
                "Category": {
                    "select": {
                        "options": [
                            {"name": "Core", "color": "blue"},
                            {"name": "Thematic", "color": "purple"},
                            {"name": "Speculative", "color": "red"},
                        ]
                    }
                },
                "Amount": {"number": {"format": "euro"}},
                "Quantity": {"number": {"format": "number"}},
                "Avg Price": {"number": {"format": "euro"}},
                "Current Price": {"number": {"format": "euro"}}, # To be updated by Tycoon
                "Last Updated": {"date": {}},
            }
        )
        return db["id"]

    def _create_goals_db(self, parent_id: str) -> str:
        """Creates Goals 2026 DB."""
        db = self.client.databases.create(
            parent={"type": "page_id", "page_id": parent_id},
            title=[{"type": "text", "text": {"content": "🎯 Goals 2026"}}],
            properties={
                "Goal": {"title": {}},
                "Status": {
                    "status": {
                        "options": [
                            {"name": "Not Started", "color": "gray"},
                            {"name": "In Progress", "color": "blue"},
                            {"name": "Achieved", "color": "green"},
                            {"name": "Behind", "color": "red"},
                        ]
                    }
                },
                "Quarter": {
                    "select": {
                        "options": [
                            {"name": "Q1", "color": "blue"},
                            {"name": "Q2", "color": "green"},
                            {"name": "Q3", "color": "yellow"},
                            {"name": "Q4", "color": "orange"},
                            {"name": "Year", "color": "purple"},
                        ]
                    }
                },
                "Progress": {"number": {"format": "percent"}},
                "Area": {
                    "select": {
                        "options": [
                            {"name": "Career", "color": "blue"},
                            {"name": "Health", "color": "green"},
                            {"name": "Finance", "color": "yellow"},
                            {"name": "Personal", "color": "pink"},
                        ]
                    }
                },
            }
        )
        return db["id"]

    def _update_env_file(self, ids: dict[str, str]):
        """Updates the .env file with new IDs."""
        env_path = ".env"
        
        # Map internal keys to env vars
        key_map = {
            "tasks": "NOTION_TASKS_DATABASE_ID",
            "knowledge": "NOTION_KNOWLEDGE_DATABASE_ID",
            "crm": "NOTION_CRM_DATABASE_ID",
            "finance": "NOTION_FINANCE_DATABASE_ID",
            "goals": "NOTION_GOALS_DATABASE_ID",
        }
        
        try:
            lines = []
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    lines = f.readlines()
            
            # Helper to check if key exists
            existing_keys = {line.split("=")[0].strip() for line in lines if "=" in line}
            
            new_lines = []
            for line in lines:
                key = line.split("=")[0].strip()
                # If this line is one of our keys, skip it (we'll append fresh ones)
                if key not in key_map.values():
                    new_lines.append(line)
            
            # Append new keys
            new_lines.append("\n# Notion Databases (Auto-generated)\n")
            for internal_key, env_key in key_map.items():
                if internal_key in ids:
                    new_lines.append(f"{env_key}={ids[internal_key]}\n")
            
            # Write back
            with open(env_path, "w") as f:
                f.writelines(new_lines)
                
            logger.info("Updated .env file with new Database IDs.")
            
        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")

