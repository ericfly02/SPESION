"""Background Task Queue — Persistent async task execution.

Long-running autonomous plans (phone calls, multi-step browser workflows)
run in the background.  Users can check progress from Telegram/Discord.

Tasks are persisted in SQLite so they survive restarts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    user_id: str = "default"
    status: TaskStatus = TaskStatus.QUEUED
    result: Any = None
    error: str | None = None
    progress: int = 0            # 0-100
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    plan_json: str | None = None  # serialized Plan if autonomous


class TaskQueue:
    """SQLite-backed task queue with async worker."""

    def __init__(self, db_path: str = "./data/task_queue.db"):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._handlers: dict[str, Callable] = {}
        self._worker_running = False
        self._lock = threading.Lock()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    user_id TEXT DEFAULT 'default',
                    status TEXT DEFAULT 'queued',
                    result TEXT,
                    error TEXT,
                    progress INTEGER DEFAULT 0,
                    created_at REAL,
                    started_at REAL,
                    completed_at REAL,
                    plan_json TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)
            """)

    # ─── Queue operations ─────────────────────────────────────────────────

    def enqueue(self, task: BackgroundTask) -> str:
        """Add a task to the queue. Returns task ID."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO tasks (id, name, description, user_id, status,
                   progress, created_at, plan_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task.id, task.name, task.description, task.user_id,
                 task.status.value, task.progress, task.created_at, task.plan_json),
            )
        logger.info(f"Task queued: {task.id} — {task.name}")
        return task.id

    def get_task(self, task_id: str) -> BackgroundTask | None:
        """Get task by ID."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def list_tasks(
        self,
        user_id: str | None = None,
        status: TaskStatus | None = None,
        limit: int = 20,
    ) -> list[BackgroundTask]:
        """List tasks with optional filters."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[Any] = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if status:
            query += " AND status = ?"
            params.append(status.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_task(r) for r in rows]

    def update_task(self, task_id: str, **kwargs):
        """Update task fields."""
        allowed = {"status", "result", "error", "progress", "started_at", "completed_at"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        # Serialize enums and complex types
        if "status" in updates and isinstance(updates["status"], TaskStatus):
            updates["status"] = updates["status"].value
        if "result" in updates and not isinstance(updates["result"], str):
            updates["result"] = json.dumps(updates["result"], default=str)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued task. Returns True if cancelled."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "UPDATE tasks SET status = 'cancelled' WHERE id = ? AND status = 'queued'",
                (task_id,),
            )
            return cursor.rowcount > 0

    def cleanup_old(self, days: int = 30):
        """Remove completed/failed tasks older than N days."""
        cutoff = time.time() - (days * 86400)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM tasks WHERE status IN ('completed', 'failed', 'cancelled') AND created_at < ?",
                (cutoff,),
            )

    # ─── Worker ───────────────────────────────────────────────────────────

    def register_handler(self, task_name: str, handler: Callable):
        """Register a handler function for a task type."""
        self._handlers[task_name] = handler

    async def start_worker(self):
        """Start the background worker that processes queued tasks."""
        if self._worker_running:
            return
        self._worker_running = True
        logger.info("Background task worker started")

        while self._worker_running:
            try:
                await self._process_next()
            except Exception as e:
                logger.error(f"Task worker error: {e}")
            await asyncio.sleep(2)

    def stop_worker(self):
        self._worker_running = False

    async def _process_next(self):
        """Pick the next queued task and execute it."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tasks WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()

        if not row:
            return

        task = self._row_to_task(row)
        handler = self._handlers.get(task.name)

        if handler is None:
            # Try the generic autonomous plan handler
            if task.plan_json:
                handler = self._execute_autonomous_plan
            else:
                self.update_task(task.id, status=TaskStatus.FAILED, error=f"No handler for: {task.name}")
                return

        self.update_task(task.id, status=TaskStatus.RUNNING, started_at=time.time())
        logger.info(f"Executing task: {task.id} — {task.name}")

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(task)
            else:
                result = handler(task)

            self.update_task(
                task.id,
                status=TaskStatus.COMPLETED,
                result=result,
                progress=100,
                completed_at=time.time(),
            )
            logger.info(f"Task completed: {task.id}")

        except Exception as e:
            self.update_task(
                task.id,
                status=TaskStatus.FAILED,
                error=str(e),
                completed_at=time.time(),
            )
            logger.error(f"Task failed: {task.id} — {e}")

    def _execute_autonomous_plan(self, task: BackgroundTask) -> str:
        """Execute a serialized autonomous plan."""
        from src.autonomous.planner import Plan, PlanExecutor

        plan_data = json.loads(task.plan_json)
        # Reconstruct plan (simplified — works for the common case)
        plan = Plan(goal=plan_data.get("goal", ""))
        from src.autonomous.planner import PlanStep, StepCategory
        for s in plan_data.get("steps", []):
            plan.steps.append(PlanStep(
                order=s.get("order", 0),
                description=s.get("description", ""),
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args", {}),
                category=StepCategory(s.get("category", "safe")),
                approval_message=s.get("approval_message"),
            ))

        # Get all tools
        tool_map = self._collect_all_tools()
        executor = PlanExecutor(tool_map=tool_map)
        result_plan = executor.run(plan)
        return result_plan.summary()

    def _collect_all_tools(self) -> dict:
        """Collect all registered tools into a name→tool map."""
        tools: dict[str, Any] = {}
        try:
            from src.tools.phone_tool import create_phone_tools
            for t in create_phone_tools():
                tools[t.name] = t
        except Exception:
            pass
        try:
            from src.tools.email_tool import create_email_tools
            for t in create_email_tools():
                tools[t.name] = t
        except Exception:
            pass
        try:
            from src.tools.browser_tool import create_browser_tools
            for t in create_browser_tools():
                tools[t.name] = t
        except Exception:
            pass
        try:
            from src.tools.calendar_mcp import create_calendar_tools
            for t in create_calendar_tools():
                tools[t.name] = t
        except Exception:
            pass
        try:
            from src.tools.notion_mcp import create_notion_tools
            for t in create_notion_tools():
                tools[t.name] = t
        except Exception:
            pass
        return tools

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _row_to_task(self, row) -> BackgroundTask:
        return BackgroundTask(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            user_id=row["user_id"] or "default",
            status=TaskStatus(row["status"]),
            result=row["result"],
            error=row["error"],
            progress=row["progress"] or 0,
            created_at=row["created_at"] or 0,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            plan_json=row["plan_json"],
        )


# ─── Singleton ────────────────────────────────────────────────────────────────

_queue: TaskQueue | None = None


def get_task_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue
