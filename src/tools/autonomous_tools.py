"""Autonomous Action Tools — LangChain tools for autonomous plan execution.

These are the tools that agents (especially Executive & Companion) use
to trigger autonomous multi-step plans.  The planner decomposes complex
goals into steps and executes them with approval gates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def execute_autonomous_plan(
    goal: str,
    background: bool = False,
) -> dict[str, Any]:
    """Plan and execute a complex multi-step task autonomously.

    Use this when the user asks SPESION to DO something in the real world:
    - "Call Endesa about my wrong bill"
    - "Email my landlord about the broken pipe"
    - "Find the cheapest flight to London and book it"
    - "Submit a complaint on the Vodafone website"
    - "Check my package tracking status"

    The planner will:
    1. Break the goal into concrete steps
    2. Ask for user approval before dangerous actions (calls, emails)
    3. Execute each step using the available tools
    4. Return a full execution report

    Args:
        goal: Natural language description of what to accomplish
        background: If True, queue the plan for background execution
                    and return immediately with a task ID.

    Returns:
        Execution report or task ID (if background).
    """
    from src.autonomous.planner import get_planner, PlanExecutor

    # Collect all available tools
    all_tools = _collect_all_tools()
    planner = get_planner(tools=all_tools)

    # Generate the plan
    plan = planner.generate_plan(goal)

    if background:
        # Queue for background execution
        from src.autonomous.task_queue import get_task_queue, BackgroundTask
        import dataclasses

        task = BackgroundTask(
            name="autonomous_plan",
            description=goal,
            plan_json=json.dumps({
                "goal": plan.goal,
                "steps": [
                    {
                        "order": s.order,
                        "description": s.description,
                        "tool_name": s.tool_name,
                        "tool_args": s.tool_args,
                        "category": s.category.value,
                        "approval_message": s.approval_message,
                    }
                    for s in plan.steps
                ],
            }),
        )
        queue = get_task_queue()
        task_id = queue.enqueue(task)
        return {
            "mode": "background",
            "task_id": task_id,
            "plan_preview": plan.summary(),
            "message": f"Plan queued for background execution. Task ID: {task_id}",
        }

    # Execute immediately (blocking)
    tool_map = {t.name: t for t in all_tools}

    # Create approval callback (sync — blocks until user responds)
    from src.autonomous.approval import create_approval_callback
    approval_cb = create_approval_callback(user_id="default")

    executor = PlanExecutor(
        tool_map=tool_map,
        approval_callback=approval_cb,
        max_retries=2,
    )

    result_plan = executor.run(plan)

    return {
        "mode": "immediate",
        "status": result_plan.status,
        "report": result_plan.summary(),
        "execution_log": result_plan.execution_log,
        "steps_completed": sum(1 for s in result_plan.steps if s.status.value == "success"),
        "steps_total": len(result_plan.steps),
    }


@tool
def check_task_status(task_id: str) -> dict[str, Any]:
    """Check the status of a background autonomous task.

    Args:
        task_id: The task ID returned by execute_autonomous_plan.

    Returns:
        Dict with current status, progress, and result if completed.
    """
    from src.autonomous.task_queue import get_task_queue

    queue = get_task_queue()
    task = queue.get_task(task_id)

    if not task:
        return {"error": f"Task not found: {task_id}"}

    return {
        "task_id": task.id,
        "name": task.name,
        "description": task.description,
        "status": task.status.value,
        "progress": task.progress,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }


@tool
def list_background_tasks(
    status: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """List recent background tasks.

    Args:
        status: Filter by status: "queued", "running", "completed", "failed"
        limit: Max number of tasks to return

    Returns:
        List of task summaries.
    """
    from src.autonomous.task_queue import get_task_queue, TaskStatus

    queue = get_task_queue()
    ts = TaskStatus(status) if status else None
    tasks = queue.list_tasks(status=ts, limit=limit)

    return [
        {
            "task_id": t.id,
            "name": t.name,
            "description": t.description[:100],
            "status": t.status.value,
            "progress": t.progress,
            "created_at": t.created_at,
        }
        for t in tasks
    ]


@tool
def get_pending_approvals() -> list[dict[str, Any]]:
    """Get all pending approval requests waiting for user response.

    Returns:
        List of approvals with step_id, message, and remaining time.
    """
    from src.autonomous.approval import get_pending_approvals as _get
    return _get()


@tool
def respond_approval(step_id: str, approved: bool) -> dict[str, Any]:
    """Approve or reject a pending autonomous action.

    Args:
        step_id: The step ID from get_pending_approvals
        approved: True to approve, False to reject

    Returns:
        Confirmation dict.
    """
    from src.autonomous.approval import respond_to_approval

    success = respond_to_approval(step_id, approved)
    if success:
        return {
            "step_id": step_id,
            "action": "approved" if approved else "rejected",
            "message": f"Step {'approved ✅' if approved else 'rejected 🚫'}",
        }
    return {"error": f"Approval not found or expired: {step_id}"}


# ─── Factory ──────────────────────────────────────────────────────────────────

def create_autonomous_tools() -> list:
    """Return all autonomous execution tools."""
    return [
        execute_autonomous_plan,
        check_task_status,
        list_background_tasks,
        get_pending_approvals,
        respond_approval,
    ]


# ─── Helper ──────────────────────────────────────────────────────────────────

def _collect_all_tools() -> list:
    """Collect all available tools from all modules."""
    tools = []
    factories = [
        ("src.tools.phone_tool", "create_phone_tools"),
        ("src.tools.email_tool", "create_email_tools"),
        ("src.tools.browser_tool", "create_browser_tools"),
        ("src.tools.calendar_mcp", "create_calendar_tools"),
        ("src.tools.notion_mcp", "create_notion_tools"),
        ("src.tools.search_tool", "create_search_tools"),
        ("src.tools.finance_tools", "create_finance_tools"),
    ]
    for module_path, fn_name in factories:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            factory = getattr(mod, fn_name, None)
            if factory:
                tools.extend(factory())
        except Exception as e:
            logger.debug(f"Could not load tools from {module_path}: {e}")
    return tools
