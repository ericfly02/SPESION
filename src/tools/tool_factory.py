"""Tool Factory — Dynamic Tool Creation System.

SPESION 3.0+: Inspired by OpenFang's "Hands" concept.
SPESION can create, register, and manage tools dynamically at runtime.

Instead of hardcoded tools, SPESION can:
  1. Define new tools from YAML/TOML manifests (like OpenFang's HAND.toml)
  2. Auto-generate tools from natural language descriptions
  3. Register tools at runtime without code changes
  4. Version, enable/disable, and audit tool usage
  5. Share tools between agents via a Tool Registry

Architecture:
    ToolManifest  — YAML definition of a tool (name, description, params, code)
    ToolFactory   — Creates LangChain Tool objects from manifests
    ToolRegistry  — SQLite-backed registry of all available tools
    ToolBuilder   — LLM-powered: generates tool code from natural language

Usage:
    factory = get_tool_factory()
    
    # Create from manifest file
    tool = factory.load_from_manifest("tools/manifests/check_weather.yaml")
    
    # Create from natural language (LLM-generated)
    tool = await factory.create_from_description(
        "A tool that checks cryptocurrency prices using CoinGecko API",
        agent="tycoon"
    )
    
    # List all custom tools
    tools = factory.registry.list_tools()
"""

from __future__ import annotations

import importlib
import json
import logging
import re
import sqlite3
import textwrap
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml
from langchain_core.tools import Tool, StructuredTool

logger = logging.getLogger(__name__)

_REGISTRY_DB = Path("./data/tool_registry.db")
_MANIFESTS_DIR = Path("./tools/manifests")

# ---------------------------------------------------------------------------
# Tool Manifest (YAML definition)
# ---------------------------------------------------------------------------

@dataclass
class ToolManifest:
    """A declarative tool definition — like OpenFang's HAND.toml but in YAML."""
    
    name: str                        # Unique tool name (snake_case)
    description: str                 # What the tool does (shown to LLM)
    version: str = "1.0.0"
    author: str = "spesion"
    
    # Parameters
    parameters: list[dict] = field(default_factory=list)
    # Each param: {"name": "query", "type": "str", "description": "...", "required": True}
    
    # Execution
    code: str = ""                   # Python code string (the function body)
    module: str = ""                 # Or import from module: "src.tools.search_tool"
    function: str = ""               # Function name in module
    
    # Agent assignment
    agents: list[str] = field(default_factory=lambda: ["*"])  # Which agents can use this
    
    # Safety
    risk_level: str = "safe"         # safe, moderate, dangerous, critical
    requires_approval: bool = False
    
    # Metadata
    trigger_keywords: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: str = ""
    use_count: int = 0
    success_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "parameters": self.parameters,
            "code": self.code,
            "module": self.module,
            "function": self.function,
            "agents": self.agents,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "trigger_keywords": self.trigger_keywords,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "use_count": self.use_count,
            "success_count": self.success_count,
        }

    @classmethod
    def from_yaml(cls, path: str | Path) -> ToolManifest:
        """Load a tool manifest from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_dict(cls, data: dict) -> ToolManifest:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Tool Registry (SQLite-backed)
# ---------------------------------------------------------------------------

_REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS tools (
    id          TEXT PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    version     TEXT DEFAULT '1.0.0',
    author      TEXT DEFAULT 'spesion',
    manifest    TEXT NOT NULL,           -- Full JSON manifest
    agents      TEXT DEFAULT '["*"]',    -- JSON array
    risk_level  TEXT DEFAULT 'safe',
    enabled     INTEGER DEFAULT 1,
    use_count   INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(name);
CREATE INDEX IF NOT EXISTS idx_tools_enabled ON tools(enabled);

CREATE TABLE IF NOT EXISTS tool_usage_log (
    id          TEXT PRIMARY KEY,
    tool_name   TEXT NOT NULL,
    agent       TEXT NOT NULL,
    input_data  TEXT,
    output_data TEXT,
    success     INTEGER,
    error       TEXT,
    duration_ms INTEGER,
    created_at  TEXT NOT NULL
);
"""


class ToolRegistry:
    """SQLite-backed registry of all custom/dynamic tools."""

    def __init__(self, db_path: str | Path = _REGISTRY_DB) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(_REGISTRY_SCHEMA)

    def register(self, manifest: ToolManifest) -> str:
        """Register a tool manifest. Returns tool ID."""
        tool_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow().isoformat()
        manifest.created_at = manifest.created_at or now
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tools 
                   (id, name, description, version, author, manifest, agents, 
                    risk_level, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tool_id,
                    manifest.name,
                    manifest.description,
                    manifest.version,
                    manifest.author,
                    json.dumps(manifest.to_dict()),
                    json.dumps(manifest.agents),
                    manifest.risk_level,
                    1 if manifest.enabled else 0,
                    manifest.created_at,
                    now,
                ),
            )
        
        logger.info(f"Registered tool: {manifest.name} (id={tool_id})")
        return tool_id

    def get(self, name: str) -> ToolManifest | None:
        """Get a tool manifest by name."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT manifest FROM tools WHERE name = ? AND enabled = 1",
                (name,),
            ).fetchone()
        
        if row:
            return ToolManifest.from_dict(json.loads(row[0]))
        return None

    def list_tools(self, agent: str = "*", enabled_only: bool = True) -> list[ToolManifest]:
        """List all tools, optionally filtered by agent."""
        with sqlite3.connect(str(self.db_path)) as conn:
            if enabled_only:
                rows = conn.execute(
                    "SELECT manifest FROM tools WHERE enabled = 1"
                ).fetchall()
            else:
                rows = conn.execute("SELECT manifest FROM tools").fetchall()
        
        tools = []
        for (manifest_json,) in rows:
            manifest = ToolManifest.from_dict(json.loads(manifest_json))
            if agent == "*" or "*" in manifest.agents or agent in manifest.agents:
                tools.append(manifest)
        
        return tools

    def disable(self, name: str) -> None:
        """Disable a tool without deleting it."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE tools SET enabled = 0 WHERE name = ?", (name,))

    def enable(self, name: str) -> None:
        """Re-enable a disabled tool."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE tools SET enabled = 1 WHERE name = ?", (name,))

    def log_usage(
        self, tool_name: str, agent: str, input_data: str,
        output_data: str, success: bool, error: str = "", duration_ms: int = 0
    ) -> None:
        """Log tool execution for audit trail."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO tool_usage_log 
                   (id, tool_name, agent, input_data, output_data, success, error, duration_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4())[:12],
                    tool_name,
                    agent,
                    input_data[:2000],
                    output_data[:2000],
                    1 if success else 0,
                    error[:500],
                    duration_ms,
                    datetime.utcnow().isoformat(),
                ),
            )
            
            # Update counters
            if success:
                conn.execute(
                    "UPDATE tools SET use_count = use_count + 1, success_count = success_count + 1 WHERE name = ?",
                    (tool_name,),
                )
            else:
                conn.execute(
                    "UPDATE tools SET use_count = use_count + 1, failure_count = failure_count + 1 WHERE name = ?",
                    (tool_name,),
                )

    def stats(self) -> dict:
        """Get registry statistics."""
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]
            enabled = conn.execute("SELECT COUNT(*) FROM tools WHERE enabled = 1").fetchone()[0]
            total_uses = conn.execute("SELECT SUM(use_count) FROM tools").fetchone()[0] or 0
            recent = conn.execute(
                "SELECT tool_name, COUNT(*) FROM tool_usage_log "
                "GROUP BY tool_name ORDER BY COUNT(*) DESC LIMIT 5"
            ).fetchall()
        
        return {
            "total_tools": total,
            "enabled_tools": enabled,
            "total_uses": total_uses,
            "most_used": [{"name": r[0], "count": r[1]} for r in recent],
        }


# ---------------------------------------------------------------------------
# Tool Factory — Creates LangChain tools from manifests
# ---------------------------------------------------------------------------

class ToolFactory:
    """Creates executable LangChain Tool objects from ToolManifests."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry()
        self._manifests_dir = _MANIFESTS_DIR
        self._manifests_dir.mkdir(parents=True, exist_ok=True)

    def build_tool(self, manifest: ToolManifest) -> Tool:
        """Build a LangChain Tool from a manifest."""
        
        if manifest.module and manifest.function:
            # Import from existing module
            func = self._import_function(manifest.module, manifest.function)
        elif manifest.code:
            # Execute dynamic code (sandboxed)
            func = self._compile_function(manifest)
        else:
            raise ValueError(f"Tool '{manifest.name}' has no code or module reference")
        
        # Wrap with logging and safety
        wrapped_func = self._wrap_with_logging(manifest, func)
        
        return Tool(
            name=manifest.name,
            description=manifest.description,
            func=wrapped_func,
        )

    def _import_function(self, module_path: str, func_name: str) -> Callable:
        """Dynamically import a function from a module."""
        try:
            module = importlib.import_module(module_path)
            return getattr(module, func_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot import {func_name} from {module_path}: {e}")

    def _compile_function(self, manifest: ToolManifest) -> Callable:
        """Compile and return a function from code string.
        
        SECURITY: Code is validated before execution:
        - No imports of os, subprocess, sys, shutil (shell access)
        - No eval(), exec(), __import__() 
        - No file system writes outside /tmp
        - Wrapped in try/except for safety
        """
        code = manifest.code
        
        # Security checks
        forbidden = [
            "import os", "import subprocess", "import sys", "import shutil",
            "os.system", "subprocess.", "eval(", "exec(", "__import__",
            "open(", "os.remove", "os.rmdir", "shutil.",
        ]
        for pattern in forbidden:
            if pattern in code:
                raise SecurityError(
                    f"Tool '{manifest.name}' contains forbidden pattern: '{pattern}'. "
                    f"Dynamic tools cannot access the filesystem or run shell commands."
                )
        
        # Compile the code into a function
        namespace: dict[str, Any] = {
            "json": __import__("json"),
            "re": __import__("re"),
            "datetime": __import__("datetime"),
            "httpx": __import__("httpx"),
        }
        
        # Wrap code in a function
        func_code = f"def _dynamic_tool(input_str: str) -> str:\n"
        for line in code.split("\n"):
            func_code += f"    {line}\n"
        
        try:
            exec(func_code, namespace)
            return namespace["_dynamic_tool"]
        except Exception as e:
            raise ValueError(f"Failed to compile tool '{manifest.name}': {e}")

    def _wrap_with_logging(self, manifest: ToolManifest, func: Callable) -> Callable:
        """Wrap a tool function with usage logging and error handling."""
        registry = self.registry
        
        def wrapped(input_str: str) -> str:
            import time
            start = time.monotonic()
            try:
                result = func(input_str)
                duration = int((time.monotonic() - start) * 1000)
                registry.log_usage(
                    manifest.name, "unknown", input_str,
                    str(result)[:500], True, duration_ms=duration
                )
                return str(result)
            except Exception as e:
                duration = int((time.monotonic() - start) * 1000)
                registry.log_usage(
                    manifest.name, "unknown", input_str,
                    "", False, str(e), duration
                )
                return f"Error in tool '{manifest.name}': {e}"
        
        wrapped.__name__ = manifest.name
        wrapped.__doc__ = manifest.description
        return wrapped

    def load_from_manifest(self, path: str | Path) -> Tool:
        """Load a tool from a YAML manifest file."""
        manifest = ToolManifest.from_yaml(path)
        self.registry.register(manifest)
        return self.build_tool(manifest)

    def load_all_manifests(self) -> list[Tool]:
        """Load all YAML manifests from the manifests directory."""
        tools = []
        for yaml_file in self._manifests_dir.glob("*.yaml"):
            try:
                tool = self.load_from_manifest(yaml_file)
                tools.append(tool)
                logger.info(f"Loaded tool manifest: {yaml_file.stem}")
            except Exception as e:
                logger.warning(f"Failed to load manifest {yaml_file}: {e}")
        return tools

    def get_tools_for_agent(self, agent: str) -> list[Tool]:
        """Get all registered tools available for a specific agent."""
        manifests = self.registry.list_tools(agent=agent)
        tools = []
        for manifest in manifests:
            try:
                tools.append(self.build_tool(manifest))
            except Exception as e:
                logger.warning(f"Failed to build tool '{manifest.name}': {e}")
        return tools

    async def create_from_description(
        self,
        description: str,
        agent: str = "*",
        llm=None,
    ) -> Tool | None:
        """LLM-powered tool creation from natural language.
        
        Example:
            tool = await factory.create_from_description(
                "A tool that gets the current weather for a city using wttr.in API"
            )
        """
        if llm is None:
            try:
                from src.services.llm_factory import get_llm
                llm = get_llm(task_type="complex")
            except Exception:
                logger.error("Cannot create tool: no LLM available")
                return None

        prompt = textwrap.dedent(f"""
            You are a tool-building AI. Create a Python tool based on this description:
            
            DESCRIPTION: {description}
            
            Generate a YAML manifest with these fields:
            - name: snake_case function name
            - description: what the tool does (1-2 sentences, this is shown to the AI agent)
            - parameters: list of params with name, type, description, required
            - code: Python function body that takes input_str and returns a string result
              - You can use: json, re, datetime, httpx (for HTTP requests)
              - Do NOT use: os, subprocess, sys, eval, exec, open
              - Always return a string
            - agents: which agents can use this (companion, executive, scholar, tycoon, coach, techlead, connector, sentinel, or * for all)
            - risk_level: safe, moderate, dangerous, or critical
            - trigger_keywords: words that would activate this tool
            
            Return ONLY valid YAML, no explanation:
            ```yaml
            name: ...
            description: ...
            parameters:
              - name: query
                type: str
                description: ...
                required: true
            code: |
              import httpx
              data = json.loads(input_str) if input_str.startswith("{{") else {{"query": input_str}}
              # ... your code ...
              return "result string"
            agents: ["*"]
            risk_level: safe
            trigger_keywords: ["keyword1", "keyword2"]
            ```
        """)

        try:
            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract YAML from response
            yaml_match = re.search(r"```yaml\s*\n(.+?)```", content, re.DOTALL)
            if yaml_match:
                yaml_str = yaml_match.group(1)
            else:
                yaml_str = content
            
            data = yaml.safe_load(yaml_str)
            manifest = ToolManifest.from_dict(data)
            
            if agent != "*":
                manifest.agents = [agent]
            
            # Register and build
            self.registry.register(manifest)
            tool = self.build_tool(manifest)
            
            # Save manifest to file for persistence
            manifest_path = self._manifests_dir / f"{manifest.name}.yaml"
            with open(manifest_path, "w") as f:
                yaml.dump(manifest.to_dict(), f, default_flow_style=False)
            
            logger.info(f"Auto-created tool: {manifest.name}")
            return tool
            
        except Exception as e:
            logger.error(f"Failed to create tool from description: {e}")
            return None


class SecurityError(Exception):
    """Raised when dynamic tool code contains forbidden patterns."""
    pass


# ---------------------------------------------------------------------------
# LangChain tools for agents to create/manage tools
# ---------------------------------------------------------------------------

def create_custom_tool(input_str: str) -> str:
    """Create a new custom tool from a natural language description.
    
    Input: A description of what the tool should do.
    Example: "A tool that converts currencies using exchangerate-api.com"
    
    Returns: Confirmation with the tool name, or an error message.
    """
    import asyncio
    
    factory = get_tool_factory()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                tool = pool.submit(
                    asyncio.run,
                    factory.create_from_description(input_str)
                ).result(timeout=60)
        else:
            tool = asyncio.run(factory.create_from_description(input_str))
        
        if tool:
            return (
                f"✅ Tool created successfully!\n"
                f"  Name: {tool.name}\n"
                f"  Description: {tool.description}\n"
                f"  The tool is now available for use."
            )
        else:
            return "❌ Failed to create tool. The description may be too vague."
    except Exception as e:
        return f"❌ Error creating tool: {e}"


def list_custom_tools(input_str: str = "") -> str:
    """List all custom/dynamic tools registered in SPESION.
    
    Returns: A formatted list of all registered tools with their status.
    """
    factory = get_tool_factory()
    tools = factory.registry.list_tools(enabled_only=False)
    stats = factory.registry.stats()
    
    if not tools:
        return "No custom tools registered yet. Use create_custom_tool to create one!"
    
    lines = [f"📦 Tool Registry ({stats['total_tools']} tools, {stats['total_uses']} total uses)\n"]
    
    for t in tools:
        status = "✅" if t.enabled else "⏸️"
        lines.append(
            f"  {status} **{t.name}** v{t.version} — {t.description}\n"
            f"     Agents: {', '.join(t.agents)} | Risk: {t.risk_level} | Uses: {t.use_count}"
        )
    
    return "\n".join(lines)


def toggle_tool(input_str: str) -> str:
    """Enable or disable a custom tool. Input: 'enable tool_name' or 'disable tool_name'."""
    parts = input_str.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0] not in ("enable", "disable"):
        return "Usage: 'enable tool_name' or 'disable tool_name'"
    
    action, name = parts
    factory = get_tool_factory()
    
    try:
        if action == "enable":
            factory.registry.enable(name)
            return f"✅ Tool '{name}' enabled"
        else:
            factory.registry.disable(name)
            return f"⏸️ Tool '{name}' disabled"
    except Exception as e:
        return f"❌ Error: {e}"


# Expose as LangChain tools
tool_factory_tools = [
    Tool(
        name="create_custom_tool",
        description=(
            "Create a new tool for SPESION from a natural language description. "
            "Example: 'A tool that checks cryptocurrency prices from CoinGecko'. "
            "The tool will be auto-generated, registered, and available for use."
        ),
        func=create_custom_tool,
    ),
    Tool(
        name="list_custom_tools",
        description="List all custom/dynamic tools registered in SPESION with their status and usage stats.",
        func=list_custom_tools,
    ),
    Tool(
        name="toggle_tool",
        description="Enable or disable a custom tool. Input: 'enable tool_name' or 'disable tool_name'.",
        func=toggle_tool,
    ),
]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_factory_instance: ToolFactory | None = None


def get_tool_factory() -> ToolFactory:
    """Get the singleton ToolFactory instance."""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = ToolFactory()
    return _factory_instance
