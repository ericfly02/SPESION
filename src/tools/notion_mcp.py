"""Notion MCP - Integración con Notion API."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

def _is_free_blocks_error(e: Exception) -> bool:
    msg = str(e).lower()
    return (
        "free blocks" in msg
        or "used all of this workspace's free blocks" in msg
        or "used all of this workspaces free blocks" in msg
        or "workspace's free blocks" in msg
    )

def _free_blocks_error_response() -> dict[str, Any]:
    return {
        "error": (
            "Notion: has alcanzado el límite de blocks del workspace (plan gratis). "
            "SPESION no puede crear más páginas/filas/bloques en Notion hasta que "
            "liberes blocks o actualices el plan."
        )
    }


def _parse_markdown_text(text: str) -> list[dict[str, Any]]:
    """Convierte texto con Markdown simple a Rich Text de Notion.
    Soporta: **negrita**, [link](url)
    """
    # Regex para detectar links: [texto](url)
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    # Regex para detectar negrita: **texto**
    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')
    
    # Estrategia: 
    # 1. Encontrar todas las coincidencias de ambos tipos
    # 2. Ordenarlas por posición
    # 3. Iterar y construir la lista de rich_text
    
    rich_text = []
    current_pos = 0
    
    # Combinamos todos los tokens de interés
    tokens = []
    
    for match in link_pattern.finditer(text):
        tokens.append({
            "start": match.start(),
            "end": match.end(),
            "type": "link",
            "text": match.group(1),
            "url": match.group(2)
        })
        
    for match in bold_pattern.finditer(text):
        # Evitar solapamientos simples (prioridad a links si se solapan, o simplemente ignorar)
        # Por simplicidad, asumimos que no hay anidamiento complejo link+bold
        tokens.append({
            "start": match.start(),
            "end": match.end(),
            "type": "bold",
            "text": match.group(1)
        })
    
    # Ordenar por posición de inicio
    tokens.sort(key=lambda x: x["start"])
    
    # Filtrar solapamientos (simple: si empieza antes de que acabe el anterior, skip)
    filtered_tokens = []
    last_end = -1
    for t in tokens:
        if t["start"] >= last_end:
            filtered_tokens.append(t)
            last_end = t["end"]
            
    # Construir rich_text
    for token in filtered_tokens:
        # Texto previo al token
        if token["start"] > current_pos:
            rich_text.append({
                "type": "text",
                "text": {"content": text[current_pos:token["start"]]}
            })
            
        # El token en sí
        if token["type"] == "link":
            rich_text.append({
                "type": "text",
                "text": {
                    "content": token["text"],
                    "link": {"url": token["url"]}
                }
            })
        elif token["type"] == "bold":
            rich_text.append({
                "type": "text",
                "text": {"content": token["text"]},
                "annotations": {"bold": True}
            })
            
        current_pos = token["end"]
        
    # Texto restante final
    if current_pos < len(text):
        rich_text.append({
            "type": "text",
            "text": {"content": text[current_pos:]}
        })
        
    return rich_text if rich_text else [{"type": "text", "text": {"content": text}}]


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


def _normalize_database_id(db_id: str) -> str:
    """Normalize Notion database ID: add dashes if missing (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)."""
    if not db_id:
        return db_id
    # Remove existing dashes
    clean = db_id.replace("-", "")
    # Add dashes in the correct positions: 8-4-4-4-12
    if len(clean) == 32:
        return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"
    return db_id  # Return as-is if not 32 chars


def _query_notion_db(client, database_id: str, **kwargs) -> dict[str, Any]:
    """Compat wrapper: Notion SDK may expose query under databases.query or data_sources.query."""
    # Normalize database ID (add dashes if missing)
    db_id_normalized = _normalize_database_id(database_id)
    
    logger.debug(f"Querying Notion database: {db_id_normalized} (original: {database_id})")
    
    # Try old API first
    if hasattr(client, "databases") and hasattr(client.databases, "query"):
        try:
            return client.databases.query(database_id=db_id_normalized, **kwargs)
        except Exception as e:
            error_msg = str(e).lower()
            # If it's a "not found" error, try the new API
            if "not found" in error_msg or "object_not_found" in error_msg:
                logger.debug(f"Old API failed, trying new API: {e}")
                if hasattr(client, "data_sources") and hasattr(client.data_sources, "query"):
                    return client.data_sources.query(data_source_id=db_id_normalized, **kwargs)
            # Re-raise if it's a different error
            raise
    
    # Try new API (Data Sources)
    if hasattr(client, "data_sources") and hasattr(client.data_sources, "query"):
        return client.data_sources.query(data_source_id=db_id_normalized, **kwargs)
    
    raise AttributeError("Notion client has no databases.query nor data_sources.query")


def _create_page_in_db(client, database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
    """Compat wrapper for pages.create parent key database_id vs data_source_id."""
    # Normalize database ID (add dashes if missing)
    db_id_normalized = _normalize_database_id(database_id)
    
    try:
        return client.pages.create(parent={"database_id": db_id_normalized}, properties=properties)
    except Exception:
        # New API might require data_source_id
        return client.pages.create(parent={"data_source_id": db_id_normalized}, properties=properties)


# =============================================================================
# HERRAMIENTAS DE TASKS
# =============================================================================

@tool
def get_tasks(
    status: str | None = None,
    limit: int | None = 20,
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
        
        response = _query_notion_db(
            client,
            settings.notion.tasks_database_id,
            filter=filter_obj,
            page_size=limit if limit is not None else 20,
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
        
        response = _create_page_in_db(client, settings.notion.tasks_database_id, properties)
        
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
        if _is_free_blocks_error(e):
            return _free_blocks_error_response()
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
                "rich_text": [{
                    "type": "text",
                    "text": {"content": f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}"},
                    "annotations": {"italic": True, "color": "gray"}
                }]
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
                    clean_text = part[2:].strip()
                    blocks.append({
                        "type": "heading_1",
                        "heading_1": {"rich_text": _parse_markdown_text(clean_text)}
                    })
                elif part.startswith("## "):
                    clean_text = part[3:].strip()
                    blocks.append({
                        "type": "heading_2",
                        "heading_2": {"rich_text": _parse_markdown_text(clean_text)}
                    })
                elif part.startswith("### "):
                    clean_text = part[4:].strip()
                    blocks.append({
                        "type": "heading_3",
                        "heading_3": {"rich_text": _parse_markdown_text(clean_text)}
                    })
                # Detectar listas (bullets)
                elif part.strip().startswith("- ") or part.strip().startswith("* "):
                    # Manejar múltiples items si el bloque contiene saltos de línea internos
                    list_items = part.split("\n")
                    for item in list_items:
                        item = item.strip()
                        if item.startswith("- ") or item.startswith("* "):
                            clean_text = item[2:].strip()
                            blocks.append({
                                "type": "bulleted_list_item",
                                "bulleted_list_item": {"rich_text": _parse_markdown_text(clean_text)}
                            })
                        else:
                            # Si hay líneas sin bullet en medio, tratarlas como párrafo indentado o normal
                            blocks.append({
                                "type": "paragraph",
                                "paragraph": {"rich_text": _parse_markdown_text(item)}
                            })
                else:
                    # Párrafo normal
                    # Manejar líneas internas que podrían ser listas si el bloque no se separó por \n\n
                    lines = part.split("\n")
                    for line in lines:
                        if line.strip().startswith("- ") or line.strip().startswith("* "):
                             blocks.append({
                                "type": "bulleted_list_item",
                                "bulleted_list_item": {"rich_text": _parse_markdown_text(line.strip()[2:])}
                            })
                        else:
                             blocks.append({
                                "type": "paragraph",
                                "paragraph": {"rich_text": _parse_markdown_text(line)}
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
        if _is_free_blocks_error(e):
            return _free_blocks_error_response()
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
def setup_notion_workspace(force: bool = False) -> dict[str, Any]:
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

        # Guardrail: evitar que un mensaje casual sobre Notion vuelva a ejecutar setup.
        # Solo si force=True o faltan IDs críticos.
        # Goals DB intentionally not required (disabled to reduce Notion blocks on free plans)
        critical_ids = [
            settings.notion.tasks_database_id,
            settings.notion.knowledge_database_id,
            settings.notion.crm_database_id,
            settings.notion.finance_database_id,
            settings.notion.pills_database_id,
        ]
        has_all = all(bool(x) for x in critical_ids)
        if has_all and not force:
            return {
                "success": True,
                "skipped": True,
                "message": (
                    "Notion ya está configurado. No voy a re-ejecutar el setup "
                    "porque podría cambiar IDs. Si quieres forzar un re-setup, "
                    "llama a setup_notion_workspace(force=true)."
                ),
                "database_ids": {
                    "tasks": settings.notion.tasks_database_id,
                    "knowledge": settings.notion.knowledge_database_id,
                    "crm": settings.notion.crm_database_id,
                    "finance": settings.notion.finance_database_id,
                    "pills": settings.notion.pills_database_id,
                },
            }
            
        service = NotionSetupService(settings.notion.api_key.get_secret_value())
        ids = service.initialize_workspace(overwrite_env=force)
        
        # Actualizar configuración en memoria para uso inmediato
        settings.notion.tasks_database_id = ids["tasks"]
        settings.notion.knowledge_database_id = ids["knowledge"]
        settings.notion.crm_database_id = ids["crm"]
        settings.notion.finance_database_id = ids["finance"]
        # goals disabled
        settings.notion.pills_database_id = ids["pills"]
        
        return {
            "success": True, 
            "message": "Workspace creado correctamente y configuración actualizada. Ya puedes usar las nuevas bases de datos.",
            "database_ids": ids
        }
        
    except Exception as e:
        logger.error(f"Error en setup de Notion: {e}")
        return {"error": str(e)}


@tool
def setup_books_database(force: bool = False) -> dict[str, Any]:
    """Crea (si falta) la base de datos de libros/reading list sin re-ejecutar todo el setup."""
    try:
        from src.core.config import settings
        from src.services.notion_setup import NotionSetupService

        if not settings.notion.api_key:
            return {"error": "API Key de Notion no configurada en .env"}

        service = NotionSetupService(settings.notion.api_key.get_secret_value())
        db_id = service.ensure_books_database(overwrite_env=force)

        settings.notion.books_database_id = db_id

        return {
            "success": True,
            "database": "books",
            "id": db_id,
            "message": "Books DB lista. Ya puedes guardar libros para leer.",
        }
    except Exception as e:
        logger.error(f"Error creando Books DB: {e}")
        return {"error": str(e)}


@tool
def add_book(
    title: str,
    author: str | None = None,
    status: str = "Not started",
    category: list[str] | None = None,
    priority: str | None = None,
    url: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Añade un libro a la Reading List.

    Nota: La propiedad Status es de tipo 'status' (Notion defaults: Not started / In progress / Done).
    """
    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}

    from src.core.config import settings
    if not settings.notion.books_database_id:
        return {"error": "Books database ID no configurado. Ejecuta setup_books_database primero."}

    try:
        props: dict[str, Any] = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Status": {"status": {"name": status}},
        }
        if author:
            props["Author"] = {"rich_text": [{"text": {"content": author}}]}
        if category:
            props["Category"] = {"multi_select": [{"name": c} for c in category]}
        if priority:
            props["Priority"] = {"select": {"name": priority}}
        if url:
            props["URL"] = {"url": url}
        if notes:
            props["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

        page = client.pages.create(
            parent={"database_id": settings.notion.books_database_id},
            properties=props,
        )
        return {"created": True, "id": page["id"], "url": page.get("url", ""), "title": title}
    except Exception as e:
        logger.error(f"Error añadiendo libro: {e}")
        if _is_free_blocks_error(e):
            return _free_blocks_error_response()
        return {"error": str(e)}


@tool
def setup_trainings_database(force: bool = False) -> dict[str, Any]:
    """Crea (si falta) la base de datos de entrenos semanales sin re-ejecutar todo el setup."""
    try:
        from src.core.config import settings
        from src.services.notion_setup import NotionSetupService

        if not settings.notion.api_key:
            return {"error": "API Key de Notion no configurada en .env"}

        service = NotionSetupService(settings.notion.api_key.get_secret_value())
        db_id = service.ensure_trainings_database(overwrite_env=force)

        settings.notion.trainings_database_id = db_id

        return {
            "success": True,
            "database": "trainings",
            "id": db_id,
            "message": "Trainings DB lista. Ya puedes guardar tus entrenos semanales.",
        }
    except Exception as e:
        logger.error(f"Error creando Trainings DB: {e}")
        return {"error": str(e)}


@tool
def setup_transactions_database(force: bool = False) -> dict[str, Any]:
    """Crea (si falta) la base de datos de Transactions (trades/movimientos)."""
    try:
        from src.core.config import settings
        from src.services.notion_setup import NotionSetupService

        if not settings.notion.api_key:
            return {"error": "API Key de Notion no configurada en .env"}

        service = NotionSetupService(settings.notion.api_key.get_secret_value())
        db_id = service.ensure_transactions_database(overwrite_env=force)

        settings.notion.transactions_database_id = db_id

        return {
            "success": True,
            "database": "transactions",
            "id": db_id,
            "message": "Transactions DB lista. Ya puedes sincronizar trades automáticamente.",
        }
    except Exception as e:
        logger.error(f"Error creando Transactions DB: {e}")
        return {"error": str(e)}


@tool
def log_training_session(
    date: str,
    day: str,
    tipus_entreno: str,
    distancia_km: float | None = None,
    temps_min: float | None = None,
    ritme_min_km: str | None = None,
    pulsacions: float | None = None,
    zona: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Guarda un entreno en la DB de Trainings.

    Columns esperadas (Notion):
    - Name (title)
    - Data (date)
    - Dia (select)
    - Tipus entreno (select)
    - Distància (km) (number)
    - Temps (min) (number)
    - Ritme (min/km) (rich_text)
    - Pulsacions (number)
    - Zona (select)
    """
    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}

    from src.core.config import settings
    if not settings.notion.trainings_database_id:
        return {"error": "Trainings database ID no configurado. Ejecuta setup_trainings_database primero."}

    try:
        name = title or f"{tipus_entreno} - {date}"
        props: dict[str, Any] = {
            "Name": {"title": [{"text": {"content": name}}]},
            "Data": {"date": {"start": date}},
            "Dia": {"select": {"name": day}},
            "Tipus entreno": {"select": {"name": tipus_entreno}},
        }
        if distancia_km is not None:
            props["Distància (km)"] = {"number": float(distancia_km)}
        if temps_min is not None:
            props["Temps (min)"] = {"number": float(temps_min)}
        if ritme_min_km:
            props["Ritme (min/km)"] = {"rich_text": [{"text": {"content": ritme_min_km}}]}
        if pulsacions is not None:
            props["Pulsacions"] = {"number": float(pulsacions)}
        if zona:
            props["Zona"] = {"select": {"name": zona}}

        page = _create_page_in_db(client, settings.notion.trainings_database_id, props)

        return {"created": True, "id": page["id"], "url": page.get("url", ""), "name": name}
    except Exception as e:
        logger.error(f"Error guardando entreno: {e}")
        if _is_free_blocks_error(e):
            return _free_blocks_error_response()
        return {"error": str(e)}


@tool
def get_training_for_date(date: str) -> list[dict[str, Any]]:
    """Obtiene entrenos planificados/registrados para una fecha."""
    client = _get_notion_client()
    if client is None:
        return [{"error": "Notion no disponible"}]

    from src.core.config import settings
    if not settings.notion.trainings_database_id:
        return [{"error": "Trainings database ID no configurado"}]

    try:
        resp = _query_notion_db(
            client,
            settings.notion.trainings_database_id,
            filter={"property": "Data", "date": {"equals": date}},
            page_size=20,
        )

        out: list[dict[str, Any]] = []
        for page in resp.get("results", []):
            props = page.get("properties", {})
            title_prop = props.get("Name", {}).get("title", [])
            name = title_prop[0]["plain_text"] if title_prop else "Sin título"

            def _rt(prop_name: str) -> str:
                rt = props.get(prop_name, {}).get("rich_text", [])
                return rt[0]["plain_text"] if rt else ""

            out.append({
                "id": page.get("id", ""),
                "name": name,
                "date": props.get("Data", {}).get("date", {}).get("start", ""),
                "day": props.get("Dia", {}).get("select", {}).get("name", ""),
                "type": props.get("Tipus entreno", {}).get("select", {}).get("name", ""),
                "distance_km": props.get("Distància (km)", {}).get("number"),
                "time_min": props.get("Temps (min)", {}).get("number"),
                "pace": _rt("Ritme (min/km)"),
                "hr": props.get("Pulsacions", {}).get("number"),
                "zone": props.get("Zona", {}).get("select", {}).get("name", ""),
                "url": page.get("url", ""),
            })

        return out
    except Exception as e:
        error_msg = str(e)
        # Check for common Notion API errors
        if "Could not find database" in error_msg or "object_not_found" in error_msg.lower():
            db_id = settings.notion.trainings_database_id
            return [{"error": f"Could not find database with ID: {db_id}. Make sure the relevant pages and databases are shared with your integration."}]
        logger.error(f"Error obteniendo entrenos: {e}")
        return [{"error": str(e)}]


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
    return [
        setup_notion_workspace,
        setup_books_database,
        setup_trainings_database,
        setup_transactions_database,
    ]


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
        setup_books_database,
        setup_trainings_database,
        setup_transactions_database,
        add_book,
        log_training_session,
        get_training_for_date,
        add_portfolio_holding,
        get_portfolio_holdings,
    ]


# =============================================================================
# HERRAMIENTAS DE FINANZAS
# =============================================================================

@tool
def add_portfolio_holding(
    ticker: str,
    amount: float,
    quantity: float,
    type: str,
    category: str,
    avg_price: float | None = None,
    current_price: float | None = None,
) -> dict[str, Any]:
    """Añade o actualiza una posición en el portfolio de finanzas.
    
    Args:
        ticker: Símbolo del activo (e.g., 'AAPL', 'BTC', 'VWCE')
        amount: Valor total en Euros
        quantity: Cantidad de acciones/tokens
        type: Tipo ('ETF', 'Stock', 'Crypto', 'Cash')
        category: Categoría ('Core', 'Thematic', 'Speculative')
        current_price: Precio unitario actual (opcional)
        
    Returns:
        Dict con el resultado
    """
    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}
    
    from src.core.config import settings
    if not settings.notion.finance_database_id:
        return {"error": "Finance database ID no configurado"}
    
    db_id = settings.notion.finance_database_id
    db_id_normalized = _normalize_database_id(db_id)
    
    try:
        # Buscar si ya existe para actualizar
        existing = _query_notion_db(
            client,
            db_id,
            filter={"property": "Ticker", "title": {"equals": ticker}},
            page_size=1,
        )
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        properties = {
            "Ticker": {"title": [{"text": {"content": ticker}}]},
            "Amount": {"number": float(amount)},
            "Quantity": {"number": float(quantity)},
            "Type": {"select": {"name": type}},
            "Category": {"select": {"name": category}},
            "Last Updated": {"date": {"start": today}},
        }
        
        # Avg Price: si se proporciona explícitamente, respetarlo.
        # Si no, usar amount/quantity como fallback.
        if quantity > 0:
            if avg_price is None:
                avg_price = amount / quantity
            properties["Avg Price"] = {"number": float(avg_price)}
            
        if current_price:
            properties["Current Price"] = {"number": float(current_price)}
        
        if existing["results"]:
            # Actualizar
            page_id = existing["results"][0]["id"]
            client.pages.update(page_id=page_id, properties=properties)
            action = "updated"
        else:
            # Crear
            page_id = _create_page_in_db(client, db_id, properties)["id"]
            action = "created"
            
        return {
            "id": page_id,
            "ticker": ticker,
            "action": action,
            "success": True
        }
        
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Error gestionando holding financiero en {db_id_normalized}: {e}", exc_info=True)
        
        if _is_free_blocks_error(e):
            return _free_blocks_error_response()
        
        # Check for database not found errors
        if "could not find database" in error_msg or "object_not_found" in error_msg or "not found" in error_msg:
            return {"error": f"Could not find database with ID: {db_id_normalized} (original: {db_id}). Make sure:\n1. The database ID in .env matches the actual Notion database ID\n2. The database is shared with your Notion integration\n3. The integration has access to the root page"}
        
        return {"error": f"Error managing portfolio holding: {str(e)}"}

@tool
def get_portfolio_holdings() -> list[dict[str, Any]]:
    """Obtiene todas las posiciones del portfolio.
    
    Returns:
        Lista de holdings
    """
    client = _get_notion_client()
    if client is None:
        return [{"error": "Notion no disponible"}]
    
    from src.core.config import settings
    if not settings.notion.finance_database_id:
        return [{"error": "Finance database ID no configurado"}]
    
    db_id = settings.notion.finance_database_id
    db_id_normalized = _normalize_database_id(db_id)
    
    # Try to verify database exists first
    try:
        # Try to retrieve the database to verify it exists
        if hasattr(client, "databases") and hasattr(client.databases, "retrieve"):
            try:
                client.databases.retrieve(database_id=db_id_normalized)
                logger.debug(f"Finance database verified via retrieve: {db_id_normalized}")
            except Exception as retrieve_err:
                logger.warning(f"Could not retrieve finance database {db_id_normalized}: {retrieve_err}")
                # Continue anyway, might still work with query
    except Exception:
        pass  # Ignore verification errors, try query anyway
    
    try:
        response = _query_notion_db(client, db_id)
        
        holdings = []
        for page in response.get("results", []):
            props = page.get("properties", {})
            
            ticker_prop = props.get("Ticker", {}).get("title", [])
            ticker = ticker_prop[0]["plain_text"] if ticker_prop else "Unknown"
            
            holdings.append({
                "ticker": ticker,
                "amount": props.get("Amount", {}).get("number", 0),
                "quantity": props.get("Quantity", {}).get("number", 0),
                "avg_price": props.get("Avg Price", {}).get("number", 0),
                "type": props.get("Type", {}).get("select", {}).get("name", ""),
                "category": props.get("Category", {}).get("select", {}).get("name", ""),
                "current_price": props.get("Current Price", {}).get("number", 0),
            })
            
        return holdings
        
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Error obteniendo holdings de {db_id_normalized}: {e}", exc_info=True)
        
        # Check for common Notion API errors
        if "could not find database" in error_msg or "object_not_found" in error_msg or "not found" in error_msg:
            return [{"error": f"Could not find database with ID: {db_id_normalized} (original: {db_id}). Make sure:\n1. The database ID in .env matches the actual Notion database ID\n2. The database is shared with your Notion integration\n3. The integration has access to the root page"}]
        
        return [{"error": f"Error querying finance database: {str(e)}"}]

def create_notion_finance_tools() -> list:
    """Herramientas de Finanzas."""
    return [add_portfolio_holding, get_portfolio_holdings]


@tool
def get_transactions(
    days: int = 7,
    limit: int = 200,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Obtiene transacciones/trades desde la DB de Transactions.

    Args:
        days: Ventana hacia atrás si no se especifica start_date (default 7)
        limit: Máximo de resultados
        start_date: YYYY-MM-DD (opcional)
        end_date: YYYY-MM-DD (opcional)
    """
    client = _get_notion_client()
    if client is None:
        return [{"error": "Notion no disponible"}]

    from src.core.config import settings
    if not settings.notion.transactions_database_id:
        return [{"error": "Transactions database ID no configurado"}]

    db_id = settings.notion.transactions_database_id
    db_id_normalized = _normalize_database_id(db_id)

    try:
        from datetime import datetime, timedelta

        if not start_date:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # Notion filter: date on_or_after / on_or_before
        date_filter: dict[str, Any] = {"property": "Date", "date": {"on_or_after": start_date}}
        if end_date:
            date_filter = {
                "and": [
                    {"property": "Date", "date": {"on_or_after": start_date}},
                    {"property": "Date", "date": {"on_or_before": end_date}},
                ]
            }

        resp = _query_notion_db(
            client,
            db_id,
            filter=date_filter,
            page_size=min(limit, 100),
            sorts=[{"property": "Date", "direction": "descending"}],
        )

        out: list[dict[str, Any]] = []
        for page in resp.get("results", []):
            props = page.get("properties", {})

            def rt(prop: str) -> str:
                arr = props.get(prop, {}).get("rich_text", [])
                return arr[0]["plain_text"] if arr else ""

            title_prop = props.get("Name", {}).get("title", [])
            name = title_prop[0]["plain_text"] if title_prop else ""

            out.append({
                "id": page.get("id", ""),
                "name": name,
                "date": props.get("Date", {}).get("date", {}).get("start", ""),
                "broker": props.get("Broker", {}).get("select", {}).get("name", ""),
                "product": props.get("Product", {}).get("select", {}).get("name", ""),
                "symbol": rt("Symbol"),
                "side": props.get("Side", {}).get("select", {}).get("name", ""),
                "quantity": props.get("Quantity", {}).get("number", None),
                "price": props.get("Price", {}).get("number", None),
                "fees": props.get("Fees", {}).get("number", None),
                "currency": props.get("Currency", {}).get("select", {}).get("name", ""),
                "account": rt("Account"),
                "external_id": rt("External ID"),
            })

        return out
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Error obteniendo transactions de {db_id_normalized}: {e}", exc_info=True)
        
        # Check for common Notion API errors
        if "could not find database" in error_msg or "object_not_found" in error_msg or "not found" in error_msg:
            return [{"error": f"Could not find database with ID: {db_id_normalized} (original: {db_id}). Make sure:\n1. The database ID in .env matches the actual Notion database ID\n2. The database is shared with your Notion integration\n3. The integration has access to the root page"}]
        
        return [{"error": f"Error querying transactions database: {str(e)}"}]

