"""Notion Manager - Gestión de las 3 bases de datos de Notion."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class NotionManager:
    """Manager centralizado para las bases de datos de Notion.
    
    Gestiona 3 bases de datos maestras:
    1. Tasks: To-Do List centralizada
    2. Knowledge: Notas diarias y resúmenes de papers
    3. CRM/Finance: Datos de proyectos, contactos y gastos
    """
    
    def __init__(self) -> None:
        """Inicializa el NotionManager."""
        self._client = None
        self._settings = None
    
    @property
    def client(self):
        """Cliente de Notion (lazy init)."""
        if self._client is None:
            try:
                from notion_client import Client
                from src.core.config import settings
                
                if not settings.notion.api_key:
                    raise ValueError("Notion API key no configurada")
                
                self._client = Client(auth=settings.notion.api_key.get_secret_value())
                self._settings = settings.notion
                logger.info("NotionManager inicializado")
                
            except ImportError:
                logger.error("notion-client no instalado")
                raise
        
        return self._client
    
    @property
    def settings(self):
        """Settings de Notion."""
        if self._settings is None:
            from src.core.config import settings
            self._settings = settings.notion
        return self._settings
    
    # =========================================================================
    # TASKS DATABASE
    # =========================================================================
    
    def get_tasks(
        self,
        status: str | None = None,
        project: str | None = None,
        priority: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Obtiene tareas de la base de datos.
        
        Args:
            status: Filtrar por estado ('Todo', 'In Progress', 'Done')
            project: Filtrar por proyecto
            priority: Filtrar por prioridad ('High', 'Medium', 'Low')
            limit: Número máximo
            
        Returns:
            Lista de tareas
        """
        if not self.settings.tasks_database_id:
            return [{"error": "Tasks database ID no configurado"}]
        
        try:
            # Construir filtro
            filters = []
            if status:
                filters.append({"property": "Status", "status": {"equals": status}})
            if project:
                filters.append({"property": "Project", "select": {"equals": project}})
            if priority:
                filters.append({"property": "Priority", "select": {"equals": priority}})
            
            filter_obj = None
            if len(filters) == 1:
                filter_obj = filters[0]
            elif len(filters) > 1:
                filter_obj = {"and": filters}
            
            response = self.client.databases.query(
                database_id=self.settings.tasks_database_id,
                filter=filter_obj,
                page_size=limit,
                sorts=[
                    {"property": "Priority", "direction": "descending"},
                    {"property": "Due Date", "direction": "ascending"},
                ],
            )
            
            return self._parse_tasks(response.get("results", []))
            
        except Exception as e:
            logger.error(f"Error obteniendo tareas: {e}")
            return [{"error": str(e)}]
    
    def create_task(
        self,
        title: str,
        project: str | None = None,
        priority: str = "Medium",
        due_date: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Crea una nueva tarea.
        
        Args:
            title: Título de la tarea
            project: Proyecto asociado
            priority: Prioridad ('High', 'Medium', 'Low')
            due_date: Fecha límite (YYYY-MM-DD)
            notes: Notas adicionales
            
        Returns:
            Tarea creada
        """
        if not self.settings.tasks_database_id:
            return {"error": "Tasks database ID no configurado"}
        
        try:
            properties = {
                "Name": {"title": [{"text": {"content": title}}]},
                "Status": {"status": {"name": "Todo"}},
                "Priority": {"select": {"name": priority}},
            }
            
            if project:
                properties["Project"] = {"select": {"name": project}}
            
            if due_date:
                properties["Due Date"] = {"date": {"start": due_date}}
            
            response = self.client.pages.create(
                parent={"database_id": self.settings.tasks_database_id},
                properties=properties,
            )
            
            # Añadir notas como contenido
            if notes:
                self.client.blocks.children.append(
                    block_id=response["id"],
                    children=[{
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": notes}}]
                        }
                    }],
                )
            
            logger.info(f"Tarea creada: {title}")
            return {"id": response["id"], "title": title, "created": True}
            
        except Exception as e:
            logger.error(f"Error creando tarea: {e}")
            return {"error": str(e)}
    
    def update_task(
        self,
        task_id: str,
        status: str | None = None,
        priority: str | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        """Actualiza una tarea existente.
        
        Args:
            task_id: ID de la tarea
            status: Nuevo estado
            priority: Nueva prioridad
            due_date: Nueva fecha límite
            
        Returns:
            Resultado de la actualización
        """
        try:
            properties = {}
            
            if status:
                properties["Status"] = {"status": {"name": status}}
            if priority:
                properties["Priority"] = {"select": {"name": priority}}
            if due_date:
                properties["Due Date"] = {"date": {"start": due_date}}
            
            if not properties:
                return {"error": "No hay campos para actualizar"}
            
            self.client.pages.update(page_id=task_id, properties=properties)
            
            logger.info(f"Tarea actualizada: {task_id}")
            return {"id": task_id, "updated": True}
            
        except Exception as e:
            logger.error(f"Error actualizando tarea: {e}")
            return {"error": str(e)}
    
    # =========================================================================
    # KNOWLEDGE DATABASE
    # =========================================================================
    
    def save_paper_summary(
        self,
        title: str,
        summary: str,
        arxiv_id: str | None = None,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        """Guarda el resumen de un paper.
        
        Args:
            title: Título del paper
            summary: Resumen generado
            arxiv_id: ID de ArXiv
            authors: Autores
            categories: Categorías
            url: URL del paper
            
        Returns:
            Documento creado
        """
        if not self.settings.knowledge_database_id:
            return {"error": "Knowledge database ID no configurado"}
        
        try:
            properties = {
                "Name": {"title": [{"text": {"content": title}}]},
                "Type": {"select": {"name": "Paper"}},
                "Date": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
            }
            
            if arxiv_id:
                properties["ArXiv ID"] = {"rich_text": [{"text": {"content": arxiv_id}}]}
            
            if authors:
                properties["Authors"] = {"rich_text": [{"text": {"content": ", ".join(authors[:5])}}]}
            
            if url:
                properties["URL"] = {"url": url}
            
            response = self.client.pages.create(
                parent={"database_id": self.settings.knowledge_database_id},
                properties=properties,
            )
            
            # Añadir resumen como contenido
            self.client.blocks.children.append(
                block_id=response["id"],
                children=[
                    {
                        "type": "heading_2",
                        "heading_2": {"rich_text": [{"text": {"content": "Resumen"}}]}
                    },
                    {
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": summary}}]}
                    },
                ],
            )
            
            logger.info(f"Paper guardado: {title}")
            return {"id": response["id"], "title": title, "created": True}
            
        except Exception as e:
            logger.error(f"Error guardando paper: {e}")
            return {"error": str(e)}
    
    def save_note(
        self,
        title: str,
        content: str,
        note_type: str = "Note",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Guarda una nota en Knowledge.
        
        Args:
            title: Título de la nota
            content: Contenido
            note_type: Tipo ('Note', 'Idea', 'Learning', etc.)
            tags: Tags opcionales
            
        Returns:
            Nota creada
        """
        if not self.settings.knowledge_database_id:
            return {"error": "Knowledge database ID no configurado"}
        
        try:
            properties = {
                "Name": {"title": [{"text": {"content": title}}]},
                "Type": {"select": {"name": note_type}},
                "Date": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
            }
            
            response = self.client.pages.create(
                parent={"database_id": self.settings.knowledge_database_id},
                properties=properties,
            )
            
            self.client.blocks.children.append(
                block_id=response["id"],
                children=[{
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": content}}]}
                }],
            )
            
            logger.info(f"Nota guardada: {title}")
            return {"id": response["id"], "title": title, "created": True}
            
        except Exception as e:
            logger.error(f"Error guardando nota: {e}")
            return {"error": str(e)}
    
    # =========================================================================
    # CRM DATABASE
    # =========================================================================
    
    def get_contacts(
        self,
        company: str | None = None,
        min_strength: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Obtiene contactos del CRM.
        
        Args:
            company: Filtrar por empresa
            min_strength: Fuerza mínima de conexión
            limit: Número máximo
            
        Returns:
            Lista de contactos
        """
        if not self.settings.crm_database_id:
            return [{"error": "CRM database ID no configurado"}]
        
        try:
            filters = []
            if company:
                filters.append({"property": "Company", "rich_text": {"contains": company}})
            if min_strength:
                filters.append({"property": "Strength", "number": {"greater_than_or_equal_to": min_strength}})
            
            filter_obj = None
            if len(filters) == 1:
                filter_obj = filters[0]
            elif len(filters) > 1:
                filter_obj = {"and": filters}
            
            response = self.client.databases.query(
                database_id=self.settings.crm_database_id,
                filter=filter_obj,
                page_size=limit,
                sorts=[{"property": "Last Contact", "direction": "descending"}],
            )
            
            return self._parse_contacts(response.get("results", []))
            
        except Exception as e:
            logger.error(f"Error obteniendo contactos: {e}")
            return [{"error": str(e)}]
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _parse_tasks(self, results: list) -> list[dict[str, Any]]:
        """Parsea resultados de Notion a tareas."""
        tasks = []
        for page in results:
            props = page.get("properties", {})
            
            title_prop = props.get("Name", {}).get("title", [])
            title = title_prop[0]["plain_text"] if title_prop else "Sin título"
            
            tasks.append({
                "id": page["id"],
                "title": title,
                "status": props.get("Status", {}).get("status", {}).get("name", ""),
                "priority": props.get("Priority", {}).get("select", {}).get("name", ""),
                "project": props.get("Project", {}).get("select", {}).get("name", ""),
                "due_date": props.get("Due Date", {}).get("date", {}).get("start", ""),
                "url": page.get("url", ""),
            })
        
        return tasks
    
    def _parse_contacts(self, results: list) -> list[dict[str, Any]]:
        """Parsea resultados de Notion a contactos."""
        contacts = []
        for page in results:
            props = page.get("properties", {})
            
            title_prop = props.get("Name", {}).get("title", [])
            name = title_prop[0]["plain_text"] if title_prop else "Sin nombre"
            
            company_prop = props.get("Company", {}).get("rich_text", [])
            company = company_prop[0]["plain_text"] if company_prop else ""
            
            contacts.append({
                "id": page["id"],
                "name": name,
                "company": company,
                "strength": props.get("Strength", {}).get("number", 0),
                "last_contact": props.get("Last Contact", {}).get("date", {}).get("start", ""),
                "url": page.get("url", ""),
            })
        
        return contacts


# Singleton
_notion_manager: NotionManager | None = None


def get_notion_manager() -> NotionManager:
    """Obtiene la instancia singleton del NotionManager."""
    global _notion_manager
    if _notion_manager is None:
        _notion_manager = NotionManager()
    return _notion_manager

