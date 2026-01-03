"""Notion MCP - Integración con Notion API."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_notion_client():
    """Obtiene el cliente de Notion."""
    try:
        from notion_client import Client
        from src.core.config import settings
        
        if not settings.notion.api_key:
            logger.warning("API key de Notion no configurada")
            return None
        
        return Client(auth=settings.notion.api_key.get_secret_value())
        
    except ImportError:
        logger.error("notion-client no instalado. pip install notion-client")
        return None


# =============================================================================
# HERRAMIENTAS DE TASKS
# =============================================================================

@tool
def get_tasks(
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Obtiene tareas de la base de datos de Tasks.
    
    Args:
        status: Filtrar por estado ('Todo', 'In Progress', 'Done')
        limit: Número máximo de tareas
        
    Returns:
        Lista de tareas
    """
    client = _get_notion_client()
    if client is None:
        return [{"error": "Notion no disponible"}]
    
    from src.core.config import settings
    if not settings.notion.tasks_database_id:
        return [{"error": "Tasks database ID no configurado"}]
    
    try:
        filter_obj = None
        if status:
            filter_obj = {
                "property": "Status",
                "status": {"equals": status}
            }
        
        response = client.databases.query(
            database_id=settings.notion.tasks_database_id,
            filter=filter_obj,
            page_size=limit,
            sorts=[{"property": "Due Date", "direction": "ascending"}],
        )
        
        tasks = []
        for page in response.get("results", []):
            props = page.get("properties", {})
            
            # Extraer título
            title_prop = props.get("Name", {}).get("title", [])
            title = title_prop[0]["plain_text"] if title_prop else "Sin título"
            
            # Extraer otros campos
            tasks.append({
                "id": page["id"],
                "title": title,
                "status": props.get("Status", {}).get("status", {}).get("name", ""),
                "priority": props.get("Priority", {}).get("select", {}).get("name", ""),
                "due_date": props.get("Due Date", {}).get("date", {}).get("start", ""),
                "project": props.get("Project", {}).get("select", {}).get("name", ""),
                "url": page.get("url", ""),
            })
        
        return tasks
        
    except Exception as e:
        logger.error(f"Error obteniendo tareas: {e}")
        return [{"error": str(e)}]


@tool
def create_task(
    title: str,
    status: str = "Todo",
    priority: str | None = None,
    due_date: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Crea una nueva tarea en Notion.
    
    Args:
        title: Título de la tarea
        status: Estado inicial ('Todo', 'In Progress')
        priority: Prioridad ('High', 'Medium', 'Low')
        due_date: Fecha límite (YYYY-MM-DD)
        project: Proyecto asociado
        
    Returns:
        Dict con la tarea creada
    """
    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}
    
    from src.core.config import settings
    if not settings.notion.tasks_database_id:
        return {"error": "Tasks database ID no configurado"}
    
    try:
        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Status": {"status": {"name": status}},
        }
        
        if priority:
            properties["Priority"] = {"select": {"name": priority}}
        
        if due_date:
            properties["Due Date"] = {"date": {"start": due_date}}
        
        if project:
            properties["Project"] = {"select": {"name": project}}
        
        response = client.pages.create(
            parent={"database_id": settings.notion.tasks_database_id},
            properties=properties,
        )
        
        return {
            "id": response["id"],
            "title": title,
            "status": status,
            "url": response.get("url", ""),
            "created": True,
        }
        
    except Exception as e:
        logger.error(f"Error creando tarea: {e}")
        return {"error": str(e)}


@tool
def update_task_status(
    task_id: str,
    status: str,
) -> dict[str, Any]:
    """Actualiza el estado de una tarea.
    
    Args:
        task_id: ID de la tarea en Notion
        status: Nuevo estado ('Todo', 'In Progress', 'Done')
        
    Returns:
        Dict con resultado
    """
    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}
    
    try:
        client.pages.update(
            page_id=task_id,
            properties={
                "Status": {"status": {"name": status}}
            },
        )
        
        return {"id": task_id, "status": status, "updated": True}
        
    except Exception as e:
        logger.error(f"Error actualizando tarea: {e}")
        return {"error": str(e)}


# =============================================================================
# HERRAMIENTAS DE JOURNAL
# =============================================================================

@tool
def create_journal_entry(
    content: str,
    mood: str | None = None,
    energy: int | None = None,
    gratitude: list[str] | None = None,
) -> dict[str, Any]:
    """Crea una entrada de diario en Notion.
    
    Args:
        content: Contenido del journal
        mood: Estado de ánimo ('Great', 'Good', 'Okay', 'Bad')
        energy: Nivel de energía (1-10)
        gratitude: Lista de cosas por las que agradecer
        
    Returns:
        Dict con la entrada creada
    """
    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}
    
    from src.core.config import settings
    if not settings.notion.knowledge_database_id:
        return {"error": "Knowledge database ID no configurado"}
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        title = f"Journal - {today}"
        
        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Type": {"select": {"name": "Journal"}},
            "Date": {"date": {"start": today}},
        }
        
        if mood:
            properties["Mood"] = {"select": {"name": mood}}
        
        if energy:
            properties["Energy"] = {"number": energy}
        
        # Crear página
        response = client.pages.create(
            parent={"database_id": settings.notion.knowledge_database_id},
            properties=properties,
        )
        
        # Añadir contenido como bloques
        blocks = [
            {
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "Reflexión"}}]
                }
            },
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": content}}]
                }
            },
        ]
        
        if gratitude:
            blocks.append({
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "Gratitud"}}]
                }
            })
            for item in gratitude:
                blocks.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"text": {"content": item}}]
                    }
                })
        
        client.blocks.children.append(
            block_id=response["id"],
            children=blocks,
        )
        
        return {
            "id": response["id"],
            "title": title,
            "url": response.get("url", ""),
            "created": True,
        }
        
    except Exception as e:
        logger.error(f"Error creando journal: {e}")
        return {"error": str(e)}


# =============================================================================
# HERRAMIENTAS DE KNOWLEDGE PILLS
# =============================================================================

@tool
def create_knowledge_pill(
    title: str,
    content: str,
    categories: list[str] | None = None,
    tags: list[str] | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Crea una entrada en la base de datos de Knowledge Pills.
    
    Args:
        title: Título del briefing
        content: Contenido completo en Markdown
        categories: Categorías (AI/ML, Neuroscience, etc.)
        tags: Etiquetas adicionales
        url: URL relevante
        
    Returns:
        Dict con la entrada creada
    """
    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}
    
    from src.core.config import settings
    if not settings.notion.pills_database_id:
        return {"error": "Pills database ID no configurado. Ejecuta setup_notion_workspace primero."}
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Date": {"date": {"start": today}},
        }
        
        if categories:
            properties["Category"] = {"multi_select": [{"name": c} for c in categories]}
            
        if tags:
            properties["Tags"] = {"multi_select": [{"name": t} for t in tags]}
            
        if url:
            properties["URL"] = {"url": url}
        
        # Crear página
        response = client.pages.create(
            parent={"database_id": settings.notion.pills_database_id},
            properties=properties,
        )
        
        # Dividir contenido en bloques (párrafos) para no exceder límites de bloque de Notion (2000 chars)
        # Una estrategia simple es dividir por saltos de línea dobles
        
        blocks = []
        # Añadir timestamp
        blocks.append({
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", "annotations": {"italic": True, "color": "gray"}}}]
            }
        })
        
        # Procesar contenido markdown simple
        parts = content.split("\n\n")
        for part in parts:
            if not part.strip():
                continue
                
            if len(part) > 1900:
                # Si un párrafo es muy largo, dividirlo más
                subparts = [part[i:i+1900] for i in range(0, len(part), 1900)]
                for sub in subparts:
                    blocks.append({
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": sub}}]}
                    })
            else:
                # Detectar encabezados básicos
                if part.startswith("# "):
                    blocks.append({
                        "type": "heading_1",
                        "heading_1": {"rich_text": [{"text": {"content": part[2:]}}]}
                    })
                elif part.startswith("## "):
                    blocks.append({
                        "type": "heading_2",
                        "heading_2": {"rich_text": [{"text": {"content": part[3:]}}]}
                    })
                elif part.startswith("### "):
                    blocks.append({
                        "type": "heading_3",
                        "heading_3": {"rich_text": [{"text": {"content": part[4:]}}]}
                    })
                else:
                    blocks.append({
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": part}}]}
                    })
        
        # Subir bloques en lotes de 100 (límite de Notion API)
        for i in range(0, len(blocks), 100):
            batch = blocks[i:i+100]
            client.blocks.children.append(
                block_id=response["id"],
                children=batch,
            )
        
        return {
            "id": response["id"],
            "title": title,
            "url": response.get("url", ""),
            "created": True,
        }
        
    except Exception as e:
        logger.error(f"Error creando knowledge pill: {e}")
        return {"error": str(e)}


# =============================================================================
# HERRAMIENTAS DE CRM
# =============================================================================

@tool
def search_contacts(
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Busca contactos en el CRM de Notion.
    
    Args:
        query: Término de búsqueda (nombre o empresa)
        limit: Número máximo de resultados
        
    Returns:
        Lista de contactos
    """
    client = _get_notion_client()
    if client is None:
        return [{"error": "Notion no disponible"}]
    
    from src.core.config import settings
    if not settings.notion.crm_database_id:
        return [{"error": "CRM database ID no configurado"}]
    
    try:
        response = client.databases.query(
            database_id=settings.notion.crm_database_id,
            filter={
                "or": [
                    {"property": "Name", "title": {"contains": query}},
                    {"property": "Company", "rich_text": {"contains": query}},
                ]
            },
            page_size=limit,
        )
        
        contacts = []
        for page in response.get("results", []):
            props = page.get("properties", {})
            
            title_prop = props.get("Name", {}).get("title", [])
            name = title_prop[0]["plain_text"] if title_prop else "Sin nombre"
            
            company_prop = props.get("Company", {}).get("rich_text", [])
            company = company_prop[0]["plain_text"] if company_prop else ""
            
            contacts.append({
                "id": page["id"],
                "name": name,
                "company": company,
                "role": props.get("Role", {}).get("rich_text", [{}])[0].get("plain_text", "") if props.get("Role", {}).get("rich_text") else "",
                "how_met": props.get("How Met", {}).get("rich_text", [{}])[0].get("plain_text", "") if props.get("How Met", {}).get("rich_text") else "",
                "strength": props.get("Strength", {}).get("number", 0),
                "last_contact": props.get("Last Contact", {}).get("date", {}).get("start", ""),
                "url": page.get("url", ""),
            })
        
        return contacts
        
    except Exception as e:
        logger.error(f"Error buscando contactos: {e}")
        return [{"error": str(e)}]


@tool
def add_contact(
    name: str,
    company: str | None = None,
    role: str | None = None,
    how_met: str | None = None,
    notes: str | None = None,
    strength: int = 2,
) -> dict[str, Any]:
    """Añade un nuevo contacto al CRM.
    
    Args:
        name: Nombre del contacto
        company: Empresa
        role: Cargo/rol
        how_met: Cómo se conocieron
        notes: Notas adicionales
        strength: Fuerza de la conexión (1-5)
        
    Returns:
        Dict con el contacto creado
    """
    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}
    
    from src.core.config import settings
    if not settings.notion.crm_database_id:
        return {"error": "CRM database ID no configurado"}
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        properties = {
            "Name": {"title": [{"text": {"content": name}}]},
            "Strength": {"number": strength},
            "Last Contact": {"date": {"start": today}},
        }
        
        if company:
            properties["Company"] = {"rich_text": [{"text": {"content": company}}]}
        
        if role:
            properties["Role"] = {"rich_text": [{"text": {"content": role}}]}
        
        if how_met:
            properties["How Met"] = {"rich_text": [{"text": {"content": how_met}}]}
        
        response = client.pages.create(
            parent={"database_id": settings.notion.crm_database_id},
            properties=properties,
        )
        
        # Añadir notas como contenido si existen
        if notes:
            client.blocks.children.append(
                block_id=response["id"],
                children=[{
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": notes}}]
                    }
                }],
            )
        
        return {
            "id": response["id"],
            "name": name,
            "url": response.get("url", ""),
            "created": True,
        }
        
    except Exception as e:
        logger.error(f"Error añadiendo contacto: {e}")
        return {"error": str(e)}


# =============================================================================
# HERRAMIENTAS DE SETUP
# =============================================================================

@tool
def setup_notion_workspace() -> dict[str, Any]:
    """Inicializa todo el workspace de Notion para SPESION.
    
    Crea la página 'SPESION HQ' y las bases de datos:
    - Tasks & Projects
    - Knowledge & Journal
    - Network (CRM)
    - Finance Portfolio
    - Goals 2026
    
    Actualiza automáticamente el archivo .env con los nuevos IDs.
    
    Returns:
        Dict con los IDs de las bases de datos creadas.
    """
    try:
        from src.core.config import settings
        from src.services.notion_setup import NotionSetupService
        
        if not settings.notion.api_key:
            return {"error": "API Key de Notion no configurada en .env"}
            
        service = NotionSetupService(settings.notion.api_key.get_secret_value())
        ids = service.initialize_workspace()
        
        # Actualizar configuración en memoria para uso inmediato
        settings.notion.tasks_database_id = ids["tasks"]
        settings.notion.knowledge_database_id = ids["knowledge"]
        settings.notion.crm_database_id = ids["crm"]
        settings.notion.finance_database_id = ids["finance"]
        settings.notion.goals_database_id = ids["goals"]
        settings.notion.pills_database_id = ids["pills"]
        
        return {
            "success": True, 
            "message": "Workspace creado correctamente y configuración actualizada. Ya puedes usar las nuevas bases de datos.",
            "database_ids": ids
        }
        
    except Exception as e:
        logger.error(f"Error en setup de Notion: {e}")
        return {"error": str(e)}


# =============================================================================
# FACTORIES
# =============================================================================

def create_notion_tasks_tools() -> list:
    """Herramientas de Tasks."""
    return [get_tasks, create_task, update_task_status]


def create_notion_journal_tools() -> list:
    """Herramientas de Journal."""
    return [create_journal_entry, create_knowledge_pill]


def create_notion_crm_tools() -> list:
    """Herramientas de CRM."""
    return [search_contacts, add_contact]


def create_notion_setup_tools() -> list:
    """Herramientas de Setup."""
    return [setup_notion_workspace]


def create_notion_tools() -> list:
    """Todas las herramientas de Notion."""
    return [
        get_tasks,
        create_task,
        update_task_status,
        create_journal_entry,
        create_knowledge_pill,
        search_contacts,
        add_contact,
        setup_notion_workspace,
    ]

