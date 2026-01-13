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

    def initialize_workspace(self, *, overwrite_env: bool = False) -> dict[str, str]:
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
        ids["pills"] = self._create_pills_db(root_id)

        # 3. Update .env file (por defecto: NO sobrescribir IDs existentes)
        self._update_env_file(ids, overwrite=overwrite_env)
        
        return ids

    # -------------------------------------------------------------------------
    # EXTRA DATABASES (NO requieren re-ejecutar todo el setup)
    # -------------------------------------------------------------------------

    def ensure_books_database(self, *, overwrite_env: bool = False) -> str:
        """Crea (si falta) la DB de libros/reading list dentro del root page."""
        root_page = self._create_root_page()
        root_id = root_page["id"]

        existing = self.client.search(
            query="📚 Reading List",
            # Notion Search API (Data Sources): value must be "page" or "data_source"
            filter={"property": "object", "value": "data_source"},
        )
        if existing.get("results"):
            db_id = existing["results"][0]["id"]
            self._update_env_file({"books": db_id}, overwrite=overwrite_env)
            return db_id

        db_id = self._create_books_db(root_id)
        self._update_env_file({"books": db_id}, overwrite=overwrite_env)
        return db_id

    def ensure_trainings_database(self, *, overwrite_env: bool = False) -> str:
        """Crea (si falta) la DB de entrenos semanales dentro del root page."""
        root_page = self._create_root_page()
        root_id = root_page["id"]

        existing = self.client.search(
            query="🏃 Weekly Trainings",
            # Notion Search API (Data Sources): value must be "page" or "data_source"
            filter={"property": "object", "value": "data_source"},
        )
        if existing.get("results"):
            db_id = existing["results"][0]["id"]
            self._update_env_file({"trainings": db_id}, overwrite=overwrite_env)
            return db_id

        db_id = self._create_trainings_db(root_id)
        self._update_env_file({"trainings": db_id}, overwrite=overwrite_env)
        return db_id

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
        try:
            # Updated for new Notion API (Data Sources)
            db = self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": "🧠 Knowledge & Journal"}}],
                initial_data_source={
                    "properties": {
                        "Name": {"type": "title", "title": {}},
                        "Type": {
                            "type": "select",
                            "select": {
                                "options": [
                                    {"name": "Journal", "color": "blue"},
                                    {"name": "Paper", "color": "red"},
                                    {"name": "Note", "color": "gray"},
                                    {"name": "Insight", "color": "yellow"},
                                ]
                            }
                        },
                        "Date": {"type": "date", "date": {}},
                        "Tags": {"type": "multi_select", "multi_select": {}},
                        "Mood": {
                            "type": "select",
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
                        "Energy": {"type": "number", "number": {"format": "number"}},
                        "URL": {"type": "url", "url": {}},
                        "ArXiv ID": {"type": "rich_text", "rich_text": {}},
                        "Authors": {"type": "rich_text", "rich_text": {}},
                        "Summary": {"type": "rich_text", "rich_text": {}},
                    }
                }
            )
            return db["id"]
        except Exception as e:
            logger.error(f"Error creating Knowledge DB: {e}")
            raise

    def _create_tasks_db(self, parent_id: str) -> str:
        """Creates Tasks DB."""
        try:
            db = self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": "✅ Tasks & Projects"}}],
                initial_data_source={
                    "properties": {
                        "Name": {"type": "title", "title": {}},
                        "Status": {"type": "status", "status": {}}, 
                        "Priority": {
                            "type": "select",
                            "select": {
                                "options": [
                                    {"name": "High", "color": "red"},
                                    {"name": "Medium", "color": "yellow"},
                                    {"name": "Low", "color": "blue"},
                                ]
                            }
                        },
                        "Due Date": {"type": "date", "date": {}},
                        "Project": {
                            "type": "select",
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
                            "type": "select",
                            "select": {
                                "options": [
                                    {"name": "High (Deep Work)", "color": "red"},
                                    {"name": "Medium", "color": "yellow"},
                                    {"name": "Low (Admin)", "color": "blue"},
                                ]
                            }
                        },
                    }
                }
            )
            return db["id"]
        except Exception as e:
            logger.error(f"Error creating Tasks DB: {e}")
            raise

    def _create_crm_db(self, parent_id: str) -> str:
        """Creates Network/CRM DB."""
        try:
            db = self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": "🤝 Network (WhoHub)"}}],
                initial_data_source={
                    "properties": {
                        "Name": {"type": "title", "title": {}},
                        "Company": {"type": "rich_text", "rich_text": {}},
                        "Role": {"type": "rich_text", "rich_text": {}},
                        "Strength": {
                            "type": "select",
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
                        "Last Contact": {"type": "date", "date": {}},
                        "How Met": {"type": "rich_text", "rich_text": {}},
                        "Tags": {"type": "multi_select", "multi_select": {}},
                        "LinkedIn": {"type": "url", "url": {}},
                    }
                }
            )
            return db["id"]
        except Exception as e:
            logger.error(f"Error creating CRM DB: {e}")
            raise

    def _create_finance_db(self, parent_id: str) -> str:
        """Creates Finance Portfolio DB."""
        try:
            db = self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": "💰 Finance Portfolio"}}],
                initial_data_source={
                    "properties": {
                        "Ticker": {"type": "title", "title": {}},
                        "Type": {
                            "type": "select",
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
                            "type": "select",
                            "select": {
                                "options": [
                                    {"name": "Core", "color": "blue"},
                                    {"name": "Thematic", "color": "purple"},
                                    {"name": "Speculative", "color": "red"},
                                ]
                            }
                        },
                        "Amount": {"type": "number", "number": {"format": "euro"}},
                        "Quantity": {"type": "number", "number": {"format": "number"}},
                        "Avg Price": {"type": "number", "number": {"format": "euro"}},
                        "Current Price": {"type": "number", "number": {"format": "euro"}},
                        "Last Updated": {"type": "date", "date": {}},
                    }
                }
            )
            return db["id"]
        except Exception as e:
            logger.error(f"Error creating Finance DB: {e}")
            raise

    def _create_goals_db(self, parent_id: str) -> str:
        """Creates Goals 2026 DB."""
        try:
            db = self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": "🎯 Goals 2026"}}],
                initial_data_source={
                    "properties": {
                        "Goal": {"type": "title", "title": {}},
                        "Status": {"type": "status", "status": {}}, 
                        "Quarter": {
                            "type": "select",
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
                        "Progress": {"type": "number", "number": {"format": "percent"}},
                        "Area": {
                            "type": "select",
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
                }
            )
            return db["id"]
        except Exception as e:
            logger.error(f"Error creating Goals DB: {e}")
            raise

    def _create_pills_db(self, parent_id: str) -> str:
        """Creates Daily Knowledge Pills DB."""
        try:
            db = self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": "💊 Daily Knowledge Pills"}}],
                initial_data_source={
                    "properties": {
                        "Name": {"type": "title", "title": {}},
                        "Date": {"type": "date", "date": {}},
                        "Category": {
                            "type": "multi_select",
                            "multi_select": {
                                "options": [
                                    {"name": "AI/ML", "color": "purple"},
                                    {"name": "Neuroscience", "color": "pink"},
                                    {"name": "Finance", "color": "green"},
                                    {"name": "Tech", "color": "blue"},
                                    {"name": "Science", "color": "orange"},
                                ]
                            }
                        },
                        "Tags": {"type": "multi_select", "multi_select": {}},
                        "URL": {"type": "url", "url": {}},
                    }
                }
            )
            logger.info(f"Created Pills DB: {db['id']}")
            return db["id"]
        except Exception as e:
            logger.error(f"Error creating Pills DB: {e}")
            raise

    def _create_books_db(self, parent_id: str) -> str:
        """Creates Books / Reading List DB."""
        try:
            db = self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": "📚 Reading List"}}],
                initial_data_source={
                    "properties": {
                        "Name": {"type": "title", "title": {}},
                        "Author": {"type": "rich_text", "rich_text": {}},
                        "Status": {"type": "status", "status": {}},
                        "Category": {"type": "multi_select", "multi_select": {}},
                        "Priority": {"type": "select", "select": {"options": [
                            {"name": "High", "color": "red"},
                            {"name": "Medium", "color": "yellow"},
                            {"name": "Low", "color": "blue"},
                        ]}},
                        "Start Date": {"type": "date", "date": {}},
                        "Finish Date": {"type": "date", "date": {}},
                        "Rating": {"type": "number", "number": {"format": "number"}},
                        "URL": {"type": "url", "url": {}},
                        "Notes": {"type": "rich_text", "rich_text": {}},
                    }
                },
            )
            logger.info(f"Created Books DB: {db['id']}")
            return db["id"]
        except Exception as e:
            logger.error(f"Error creating Books DB: {e}")
            raise

    def _create_trainings_db(self, parent_id: str) -> str:
        """Creates Weekly Trainings DB."""
        try:
            db = self.client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": "🏃 Weekly Trainings"}}],
                initial_data_source={
                    "properties": {
                        "Name": {"type": "title", "title": {}},
                        "Data": {"type": "date", "date": {}},
                        "Dia": {"type": "select", "select": {"options": [
                            {"name": "Dilluns", "color": "blue"},
                            {"name": "Dimarts", "color": "blue"},
                            {"name": "Dimecres", "color": "blue"},
                            {"name": "Dijous", "color": "blue"},
                            {"name": "Divendres", "color": "blue"},
                            {"name": "Dissabte", "color": "blue"},
                            {"name": "Diumenge", "color": "blue"},
                        ]}},
                        "Tipus entreno": {"type": "select", "select": {"options": [
                            {"name": "Easy", "color": "green"},
                            {"name": "Intervals", "color": "red"},
                            {"name": "Tempo", "color": "orange"},
                            {"name": "Long", "color": "yellow"},
                            {"name": "Gym", "color": "purple"},
                            {"name": "Rest", "color": "gray"},
                        ]}},
                        "Distància (km)": {"type": "number", "number": {"format": "number"}},
                        "Temps (min)": {"type": "number", "number": {"format": "number"}},
                        "Ritme (min/km)": {"type": "rich_text", "rich_text": {}},
                        "Pulsacions": {"type": "number", "number": {"format": "number"}},
                        "Zona": {"type": "select", "select": {"options": [
                            {"name": "Z1", "color": "green"},
                            {"name": "Z2", "color": "blue"},
                            {"name": "Z3", "color": "yellow"},
                            {"name": "Z4", "color": "orange"},
                            {"name": "Z5", "color": "red"},
                        ]}},
                    }
                },
            )
            logger.info(f"Created Trainings DB: {db['id']}")
            return db["id"]
        except Exception as e:
            logger.error(f"Error creating Trainings DB: {e}")
            raise

    def _update_env_file(self, ids: dict[str, str], *, overwrite: bool = False) -> None:
        """Updates the .env file with new IDs.

        IMPORTANT:
        - Por defecto NO sobrescribe IDs existentes para evitar que un setup accidental
          cambie los IDs y rompa el sistema.
        - Si overwrite=True, reemplaza los IDs existentes.
        """
        env_path = ".env"
        
        # Map internal keys to env vars
        key_map = {
            "tasks": "NOTION_TASKS_DATABASE_ID",
            "knowledge": "NOTION_KNOWLEDGE_DATABASE_ID",
            "crm": "NOTION_CRM_DATABASE_ID",
            "finance": "NOTION_FINANCE_DATABASE_ID",
            "goals": "NOTION_GOALS_DATABASE_ID",
            "pills": "NOTION_PILLS_DATABASE_ID",
            "books": "NOTION_BOOKS_DATABASE_ID",
            "trainings": "NOTION_TRAININGS_DATABASE_ID",
        }
        
        try:
            lines: list[str] = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            # Parse existing key->value (muy simple, preservamos comentarios/orden)
            existing: dict[str, str] = {}
            for line in lines:
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

            # Decide qué claves actualizar
            desired_updates: dict[str, str] = {}
            for internal_key, env_key in key_map.items():
                if internal_key not in ids:
                    continue
                if overwrite or (env_key not in existing) or (existing.get(env_key, "").strip() == ""):
                    desired_updates[env_key] = ids[internal_key]

            if not desired_updates:
                logger.info("No Notion env keys to update (already configured).")
                return

            # Reescribir líneas actualizando in-place si existen
            updated_lines: list[str] = []
            touched: set[str] = set()
            for line in lines:
                if "=" not in line:
                    updated_lines.append(line)
                    continue
                k, _ = line.split("=", 1)
                key = k.strip()
                if key in desired_updates:
                    updated_lines.append(f"{key}={desired_updates[key]}\n")
                    touched.add(key)
                else:
                    updated_lines.append(line)

            # Añadir las que no existían
            missing_keys = [k for k in desired_updates.keys() if k not in touched and k not in existing]
            if missing_keys:
                updated_lines.append("\n# Notion Databases (Auto-generated)\n")
                for k in missing_keys:
                    updated_lines.append(f"{k}={desired_updates[k]}\n")

            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)

            logger.info(
                "Updated .env file with Notion Database IDs: "
                + ", ".join(sorted(desired_updates.keys()))
            )

        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")
