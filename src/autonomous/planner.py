"""Autonomous Task Planner — Multi-step plan decomposition & execution.

Given a complex user request (e.g. "call Endesa about wrong receipt"),
the planner:

1. Decomposes the request into ordered steps.
2. Maps each step to a concrete tool invocation.
3. Inserts approval gates before *dangerous* actions (calls, emails, payments).
4. Executes steps sequentially, passing context from one to the next.
5. Retries transient failures and rolls back when possible.
6. Produces a human-readable execution report.

Architecture
============

User request
    │
    ▼
 ┌──────────┐
 │ Planner  │  LLM-based plan generation (JSON schema)
 └────┬─────┘
      │  plan = [Step, Step, …]
      ▼
 ┌──────────────────────────────┐
 │  PlanExecutor.run(plan)      │  Sequential step runner
 │  ├─ resolve_tool(step)       │  Find the right tool callable
 │  ├─ needs_approval?(step)    │  Check DANGEROUS categories
 │  ├─ request_approval()       │  Via Telegram/Discord callback
 │  ├─ invoke_tool(step, ctx)   │  Actual execution
 │  └─ update_context(result)   │  Feed output to next step
 └──────────────────────────────┘
      │
      ▼
  execution_report → user
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════

class StepCategory(str, Enum):
    """Risk classification for plan steps."""
    SAFE = "safe"                  # read-only lookups
    MODERATE = "moderate"          # write to DBs (Notion, Calendar)
    DANGEROUS = "dangerous"        # phone calls, real-money, emails to 3rd parties
    CRITICAL = "critical"          # payments, contract signing, etc.


class StepStatus(str, Enum):
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in an autonomous plan."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    order: int = 0
    description: str = ""
    tool_name: str | None = None        # name of a LangChain tool to invoke
    tool_args: dict[str, Any] = field(default_factory=dict)
    category: StepCategory = StepCategory.SAFE
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
    depends_on: list[str] = field(default_factory=list)   # IDs of prerequisite steps
    # Approval
    approval_message: str | None = None      # what to show the user
    approved_by: str | None = None


@dataclass
class Plan:
    """An ordered list of steps to accomplish a user goal."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "pending"           # pending | running | completed | failed | aborted
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    execution_log: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"📋 Plan: {self.goal}  (status={self.status})"]
        for s in self.steps:
            icon = {
                StepStatus.SUCCESS: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.RUNNING: "⏳",
                StepStatus.SKIPPED: "⏭️",
                StepStatus.AWAITING_APPROVAL: "🔐",
                StepStatus.REJECTED: "🚫",
            }.get(s.status, "⬜")
            lines.append(f"  {icon} {s.order}. {s.description}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Categories that require human approval
# ═══════════════════════════════════════════════════════════════════

APPROVAL_REQUIRED: set[StepCategory] = {
    StepCategory.DANGEROUS,
    StepCategory.CRITICAL,
}

# Tool name patterns auto-classified as dangerous
DANGEROUS_TOOL_PATTERNS: set[str] = {
    "make_phone_call",
    "send_email",
    "send_sms",
    "submit_form",
    "make_payment",
    "browser_fill_form",
    "browser_click",
}


# ═══════════════════════════════════════════════════════════════════
# Planner — LLM-based plan generation
# ═══════════════════════════════════════════════════════════════════

PLAN_GENERATION_PROMPT = """\
You are SPESION's autonomous planner. Given the user's goal and the list of
available tools, produce a JSON plan that accomplishes the goal step-by-step.

## Available tools
{tools_description}

## Rules
1. Each step must use exactly one tool (or "none" for a pure reasoning step).
2. Classify each step:
   - "safe"      → read-only (lookups, searches, checks)
   - "moderate"  → writes to user's own systems (calendar, Notion, etc.)
   - "dangerous" → contacts external parties (phone call, email, form submit)
   - "critical"  → involves real money (payment, transfer, trade)
3. For dangerous/critical steps, include an "approval_message" explaining
   what SPESION is about to do so the user can approve or reject.
4. Keep it minimal — do NOT add unnecessary steps.
5. Use output from earlier steps by referencing {{step_N_result}}.

## Output format (JSON only — no markdown fences)
{{
  "goal": "<restate the goal>",
  "steps": [
    {{
      "order": 1,
      "description": "What this step does",
      "tool_name": "tool_name_or_none",
      "tool_args": {{}},
      "category": "safe|moderate|dangerous|critical",
      "approval_message": "only if dangerous/critical, else null"
    }}
  ]
}}

## User goal
{user_goal}
"""


class AutonomousPlanner:
    """Generates executable plans from natural-language goals."""

    def __init__(self, llm=None, tools: list | None = None):
        self._llm = llm
        self._tools = tools or []
        self._tool_map: dict[str, Any] = {t.name: t for t in self._tools}

    def _get_llm(self):
        if self._llm:
            return self._llm
        try:
            from src.core.model_router import get_model_router
            router = get_model_router()
            return router.get_llm(agent_name="executive", temperature=0.2)
        except Exception:
            from src.services.llm_factory import get_llm, TaskType
            return get_llm(task_type=TaskType.COMPLEX, temperature=0.2)

    def _tools_description(self) -> str:
        lines = []
        for t in self._tools:
            desc = getattr(t, "description", "") or ""
            lines.append(f"- {t.name}: {desc[:120]}")
        return "\n".join(lines) if lines else "(no tools loaded)"

    def generate_plan(self, user_goal: str) -> Plan:
        """Use LLM to produce a Plan from a user goal."""
        llm = self._get_llm()
        prompt = PLAN_GENERATION_PROMPT.format(
            tools_description=self._tools_description(),
            user_goal=user_goal,
        )

        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)

        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from surrounding text
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
            else:
                raise ValueError(f"LLM did not produce valid JSON plan: {raw[:300]}")

        plan = Plan(goal=data.get("goal", user_goal))

        for s in data.get("steps", []):
            tool_name = s.get("tool_name")
            if tool_name == "none":
                tool_name = None
            cat = StepCategory(s.get("category", "safe"))
            # Auto-classify dangerous by tool name even if LLM said "safe"
            if tool_name and tool_name in DANGEROUS_TOOL_PATTERNS:
                cat = StepCategory.DANGEROUS

            step = PlanStep(
                order=s.get("order", 0),
                description=s.get("description", ""),
                tool_name=tool_name,
                tool_args=s.get("tool_args", {}),
                category=cat,
                approval_message=s.get("approval_message"),
            )
            plan.steps.append(step)

        # Ensure steps are sorted
        plan.steps.sort(key=lambda x: x.order)
        logger.info(f"Plan generated: {len(plan.steps)} steps for goal: {user_goal[:80]}")
        return plan


# ═══════════════════════════════════════════════════════════════════
# PlanExecutor — runs plans step by step
# ═══════════════════════════════════════════════════════════════════

class PlanExecutor:
    """Executes a Plan step by step with approval gates and retries."""

    def __init__(
        self,
        tool_map: dict[str, Any] | None = None,
        approval_callback: Callable[[PlanStep], bool] | None = None,
        max_retries: int = 2,
        step_timeout: float = 120.0,
    ):
        """
        Args:
            tool_map: {tool_name: tool_callable} — usually tool.invoke
            approval_callback: Called for dangerous steps.
                Must return True to proceed, False to skip.
                If None, dangerous steps are auto-skipped.
            max_retries: How many times to retry a failed step.
            step_timeout: Timeout per step in seconds (soft limit).
        """
        self._tool_map = tool_map or {}
        self._approval_callback = approval_callback
        self._max_retries = max_retries
        self._step_timeout = step_timeout

    def run(self, plan: Plan) -> Plan:
        """Execute all steps in order. Mutates ``plan`` in-place."""
        plan.status = "running"
        context: dict[str, Any] = {}    # accumulated results keyed by step_N_result

        for step in plan.steps:
            log_prefix = f"Step {step.order} ({step.description[:50]})"

            # --- Check dependencies ---
            if step.depends_on:
                unmet = [
                    dep for dep in step.depends_on
                    if not any(s.id == dep and s.status == StepStatus.SUCCESS for s in plan.steps)
                ]
                if unmet:
                    step.status = StepStatus.SKIPPED
                    step.error = f"Unmet dependencies: {unmet}"
                    plan.execution_log.append(f"⏭️ {log_prefix}: skipped (deps)")
                    continue

            # --- Approval gate ---
            if step.category in APPROVAL_REQUIRED:
                step.status = StepStatus.AWAITING_APPROVAL
                plan.execution_log.append(f"🔐 {log_prefix}: awaiting approval")

                if self._approval_callback:
                    approved = self._approval_callback(step)
                else:
                    # No callback → auto-reject dangerous steps for safety
                    approved = False
                    logger.warning(f"No approval callback — auto-rejecting: {step.description}")

                if approved:
                    step.status = StepStatus.APPROVED
                    plan.execution_log.append(f"✅ {log_prefix}: approved")
                else:
                    step.status = StepStatus.REJECTED
                    plan.execution_log.append(f"🚫 {log_prefix}: rejected by user")
                    continue

            # --- Execute tool ---
            if step.tool_name is None:
                # Pure reasoning step — just mark done
                step.status = StepStatus.SUCCESS
                step.result = step.description
                context[f"step_{step.order}_result"] = step.result
                plan.execution_log.append(f"💭 {log_prefix}: reasoning step (ok)")
                continue

            tool = self._tool_map.get(step.tool_name)
            if tool is None:
                step.status = StepStatus.FAILED
                step.error = f"Tool not found: {step.tool_name}"
                plan.execution_log.append(f"❌ {log_prefix}: tool not found")
                continue

            # Interpolate context references in tool_args
            resolved_args = self._resolve_args(step.tool_args, context)

            step.status = StepStatus.RUNNING
            for attempt in range(1, self._max_retries + 1):
                try:
                    result = tool.invoke(resolved_args)
                    step.result = result
                    step.status = StepStatus.SUCCESS
                    context[f"step_{step.order}_result"] = result
                    plan.execution_log.append(f"✅ {log_prefix}: success (attempt {attempt})")
                    break
                except Exception as e:
                    step.error = str(e)
                    logger.warning(f"{log_prefix}: attempt {attempt} failed: {e}")
                    if attempt < self._max_retries:
                        time.sleep(2 ** attempt)  # exponential backoff
                    else:
                        step.status = StepStatus.FAILED
                        plan.execution_log.append(
                            f"❌ {log_prefix}: failed after {self._max_retries} attempts: {e}"
                        )

        # Finalize
        all_statuses = {s.status for s in plan.steps}
        if all(s == StepStatus.SUCCESS for s in all_statuses):
            plan.status = "completed"
        elif StepStatus.FAILED in all_statuses:
            plan.status = "partial" if StepStatus.SUCCESS in all_statuses else "failed"
        elif all(s in (StepStatus.REJECTED, StepStatus.SKIPPED) for s in all_statuses):
            plan.status = "aborted"
        else:
            plan.status = "completed"

        plan.completed_at = time.time()
        logger.info(f"Plan '{plan.goal[:60]}' finished: {plan.status}")
        return plan

    def _resolve_args(self, args: dict, context: dict) -> dict:
        """Replace {step_N_result} placeholders in tool_args with real values."""
        resolved = {}
        for k, v in args.items():
            if isinstance(v, str):
                for ctx_key, ctx_val in context.items():
                    placeholder = "{" + ctx_key + "}"
                    if placeholder in v:
                        v = v.replace(placeholder, str(ctx_val))
            resolved[k] = v
        return resolved


# ═══════════════════════════════════════════════════════════════════
# Convenience singleton
# ═══════════════════════════════════════════════════════════════════

_planner: AutonomousPlanner | None = None


def get_planner(tools: list | None = None) -> AutonomousPlanner:
    """Return (or create) the global planner singleton."""
    global _planner
    if _planner is None:
        _planner = AutonomousPlanner(tools=tools or [])
    return _planner
