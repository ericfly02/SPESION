"""POST /api/v1/tools/{tool_name} — Direct tool invocation."""

from __future__ import annotations

import importlib
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import require_api_key

router = APIRouter()
logger = logging.getLogger("spesion.api.tools")


# ---------------------------------------------------------------------------
# Tool registry: tool_name → (module_path, function_name)
# ---------------------------------------------------------------------------
TOOL_REGISTRY: dict[str, tuple[str, str]] = {
    # Scholar
    "get_recent_papers": ("src.tools.arxiv_tool", "get_recent_papers"),
    "web_search": ("src.tools.search_tool", "web_search"),
    "search_news": ("src.tools.search_tool", "search_news"),
    # Coach
    "get_garmin_stats": ("src.tools.garmin_mcp", "get_garmin_stats"),
    "get_strava_activities": ("src.tools.strava_mcp", "get_strava_activities"),
    # Tycoon
    "get_stock_price": ("src.tools.finance_tools", "get_stock_price"),
    "sync_investments": ("src.tools.investments_sync", "sync_investments_to_notion"),
    # Executive
    "get_today_agenda": ("src.tools.calendar_mcp", "get_today_agenda"),
    "get_tasks": ("src.tools.notion_mcp", "get_tasks"),
    "create_task": ("src.tools.notion_mcp", "create_task"),
    # TechLead
    "get_github_file": ("src.tools.github_mcp", "get_github_file"),
    # Memory
    "save_memory": ("src.tools.memory_tools", "save_important_memory"),
    "search_memory": ("src.tools.memory_tools", "retrieve_memories"),
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ToolRequest(BaseModel):
    args: dict[str, Any] = {}


class ToolResponse(BaseModel):
    success: bool
    result: Any
    tool: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/tools", summary="List available tools")
async def list_tools(_key: str = Depends(require_api_key)):
    """Return the list of registered tools."""
    return {"tools": sorted(TOOL_REGISTRY.keys())}


@router.post("/tools/{tool_name}", response_model=ToolResponse)
async def invoke_tool(
    tool_name: str,
    req: ToolRequest,
    _key: str = Depends(require_api_key),
):
    """Invoke a SPESION tool by name with the given arguments."""
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(404, f"Tool '{tool_name}' not found. Available: {sorted(TOOL_REGISTRY)}")

    module_path, func_name = TOOL_REGISTRY[tool_name]

    try:
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    except (ImportError, AttributeError) as exc:
        raise HTTPException(500, f"Tool '{tool_name}' failed to load: {exc}") from exc

    try:
        # LangChain @tool-decorated functions expose .invoke()
        if hasattr(func, "invoke"):
            result = func.invoke(req.args)
        else:
            result = func(**req.args)
        return ToolResponse(success=True, result=result, tool=tool_name)
    except Exception as exc:
        logger.error(f"Tool {tool_name} error: {exc}", exc_info=True)
        return ToolResponse(success=False, result=str(exc), tool=tool_name)
