"""Heartbeat Runner — Proactive autonomous operation.

Inspired by OpenClaw's heartbeat system:
• Periodic agent turns without user input (default 30min)
• HEARTBEAT.md checklist processing
• Active hours configuration
• Proactive monitoring (portfolio, calendar, news)
• Memory maintenance during heartbeats
• Cron-style scheduling for specific tasks

The heartbeat makes SPESION PROACTIVE — it doesn't just wait to be asked.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore


# ---------------------------------------------------------------------------
# Heartbeat Config
# ---------------------------------------------------------------------------

class HeartbeatConfig:
    """Configuration for the heartbeat system."""

    def __init__(
        self,
        interval_minutes: int = 30,
        active_start: time = time(7, 0),
        active_end: time = time(23, 30),
        timezone: str = "Europe/Madrid",
        enabled: bool = True,
    ) -> None:
        self.interval_minutes = interval_minutes
        self.active_start = active_start
        self.active_end = active_end
        self.timezone = timezone
        self.enabled = enabled

    def is_active_hours(self) -> bool:
        """Check if we're within active hours."""
        if ZoneInfo:
            now = datetime.now(ZoneInfo(self.timezone))
        else:
            now = datetime.now()
        current_time = now.time()
        return self.active_start <= current_time <= self.active_end


# ---------------------------------------------------------------------------
# Scheduled Task
# ---------------------------------------------------------------------------

class ScheduledTask:
    """A task that runs on a schedule (cron-like)."""

    def __init__(
        self,
        name: str,
        callback: Callable[..., Coroutine],
        schedule: str,  # "every:30m", "daily:08:30", "weekly:sun:10:00"
        agent_name: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.callback = callback
        self.schedule = schedule
        self.agent_name = agent_name
        self.enabled = enabled
        self.last_run: datetime | None = None
        self.run_count: int = 0
        self.last_error: str | None = None

    def should_run(self, now: datetime) -> bool:
        """Check if this task should run now."""
        if not self.enabled:
            return False

        parts = self.schedule.split(":")

        if parts[0] == "every":
            # "every:30m" or "every:2h"
            interval_str = parts[1]
            if interval_str.endswith("m"):
                interval = timedelta(minutes=int(interval_str[:-1]))
            elif interval_str.endswith("h"):
                interval = timedelta(hours=int(interval_str[:-1]))
            else:
                interval = timedelta(minutes=int(interval_str))

            if self.last_run is None:
                return True
            return (now - self.last_run) >= interval

        elif parts[0] == "daily":
            # "daily:08:30"
            target_time = time(int(parts[1]), int(parts[2]))
            if self.last_run and self.last_run.date() == now.date():
                return False  # Already ran today
            # Run if we're within 5 minutes of the target
            diff = abs(
                (now.hour * 60 + now.minute) - (target_time.hour * 60 + target_time.minute)
            )
            return diff <= 5

        elif parts[0] == "weekly":
            # "weekly:sun:10:00"
            day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            target_day = day_map.get(parts[1].lower(), 6)
            target_time = time(int(parts[2]), int(parts[3]))

            if now.weekday() != target_day:
                return False
            if self.last_run and self.last_run.date() == now.date():
                return False
            diff = abs(
                (now.hour * 60 + now.minute) - (target_time.hour * 60 + target_time.minute)
            )
            return diff <= 5

        return False


# ---------------------------------------------------------------------------
# Heartbeat Runner
# ---------------------------------------------------------------------------

class HeartbeatRunner:
    """Manages the heartbeat cycle and scheduled tasks.

    The runner:
    1. Checks active hours
    2. Runs scheduled tasks that are due
    3. Processes HEARTBEAT.md checklist items
    4. Performs cognitive reflection (pattern detection, idea generation)
    5. Reports any important findings back to the user
    """

    def __init__(self, config: HeartbeatConfig | None = None) -> None:
        self.config = config or HeartbeatConfig()
        self.tasks: list[ScheduledTask] = []
        self._running = False
        self._beat_count = 0
        self._notifications: list[dict[str, Any]] = []

        # Register default tasks
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default heartbeat tasks."""
        self.register_task(ScheduledTask(
            name="memory_reflection",
            callback=self._task_memory_reflection,
            schedule="every:2h",
            agent_name="cognitive",
        ))
        self.register_task(ScheduledTask(
            name="pattern_detection",
            callback=self._task_pattern_detection,
            schedule="daily:22:00",
            agent_name="cognitive",
        ))
        self.register_task(ScheduledTask(
            name="idea_generation",
            callback=self._task_idea_generation,
            schedule="weekly:sun:10:00",
            agent_name="cognitive",
        ))
        self.register_task(ScheduledTask(
            name="memory_curation",
            callback=self._task_memory_curation,
            schedule="daily:03:00",
            agent_name="cognitive",
        ))
        self.register_task(ScheduledTask(
            name="health_check",
            callback=self._task_health_check,
            schedule="every:30m",
            agent_name="sentinel",
        ))

    def register_task(self, task: ScheduledTask) -> None:
        """Register a new scheduled task."""
        self.tasks.append(task)
        logger.info(f"Heartbeat task registered: {task.name} ({task.schedule})")

    # ------------------------------------------------------------------
    # Main Loop
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the heartbeat loop."""
        if not self.config.enabled:
            logger.info("Heartbeat system is disabled")
            return

        self._running = True
        logger.info(
            f"💓 Heartbeat started: interval={self.config.interval_minutes}m, "
            f"active={self.config.active_start}-{self.config.active_end}"
        )

        while self._running:
            try:
                await self._beat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            await asyncio.sleep(self.config.interval_minutes * 60)

    async def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        logger.info("💓 Heartbeat stopped")

    async def _beat(self) -> None:
        """Execute one heartbeat cycle."""
        self._beat_count += 1

        if not self.config.is_active_hours():
            logger.debug(f"Heartbeat #{self._beat_count}: outside active hours, skipping")
            return

        logger.info(f"💓 Heartbeat #{self._beat_count}")
        now = datetime.now()

        # Run due scheduled tasks
        for task in self.tasks:
            if task.should_run(now):
                try:
                    logger.info(f"  Running task: {task.name}")
                    await task.callback()
                    task.last_run = now
                    task.run_count += 1
                    task.last_error = None
                except Exception as e:
                    task.last_error = str(e)
                    logger.error(f"  Task {task.name} failed: {e}")

    # ------------------------------------------------------------------
    # Default Task Implementations
    # ------------------------------------------------------------------

    async def _task_memory_reflection(self) -> None:
        """Run cognitive reflection on recent memories."""
        from src.cognitive.reflection import get_cognitive_loop
        loop = get_cognitive_loop()
        loop.curate_memory_file()

    async def _task_pattern_detection(self) -> None:
        """Detect patterns in recent memories."""
        from src.cognitive.reflection import get_cognitive_loop
        loop = get_cognitive_loop()
        patterns = loop.detect_patterns(days=7)
        if patterns:
            self._notify(
                title="🧠 Patterns Detected",
                content="\n".join([
                    f"• {p['description']} (conf: {p.get('confidence', 0):.0%})"
                    for p in patterns[:5]
                ]),
            )

    async def _task_idea_generation(self) -> None:
        """Generate ideas from accumulated knowledge."""
        from src.cognitive.reflection import get_cognitive_loop
        loop = get_cognitive_loop()
        ideas = loop.generate_ideas()
        if ideas:
            self._notify(
                title="💡 Weekly Ideas",
                content="\n".join([
                    f"• **{idea['title']}**: {idea['description']}"
                    for idea in ideas[:5]
                ]),
            )

    async def _task_memory_curation(self) -> None:
        """Curate and update MEMORY.md."""
        from src.cognitive.reflection import get_cognitive_loop
        from src.memory.evolving_memory import get_memory_bank

        loop = get_cognitive_loop()
        bank = get_memory_bank()

        loop.curate_memory_file()
        bank.cleanup_low_confidence(threshold=0.1)

    async def _task_health_check(self) -> None:
        """Check system health."""
        from src.core.model_router import get_model_router
        router = get_model_router()
        router.refresh_availability()
        status = router.get_health_status()

        # Check for provider issues
        for provider, available in status["providers"].items():
            if not available:
                logger.warning(f"Provider {provider} is unavailable")

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _notify(self, title: str, content: str, priority: str = "normal") -> None:
        """Queue a notification for the user."""
        self._notifications.append({
            "title": title,
            "content": content,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "delivered": False,
        })

    def get_pending_notifications(self) -> list[dict[str, Any]]:
        """Get and mark pending notifications as delivered."""
        pending = [n for n in self._notifications if not n["delivered"]]
        for n in pending:
            n["delivered"] = True
        return pending

    def clear_notifications(self) -> None:
        """Clear all delivered notifications."""
        self._notifications = [n for n in self._notifications if not n["delivered"]]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Get heartbeat system status."""
        return {
            "running": self._running,
            "beat_count": self._beat_count,
            "config": {
                "interval_minutes": self.config.interval_minutes,
                "active_start": str(self.config.active_start),
                "active_end": str(self.config.active_end),
                "timezone": self.config.timezone,
            },
            "tasks": [
                {
                    "name": t.name,
                    "schedule": t.schedule,
                    "enabled": t.enabled,
                    "last_run": t.last_run.isoformat() if t.last_run else None,
                    "run_count": t.run_count,
                    "last_error": t.last_error,
                }
                for t in self.tasks
            ],
            "pending_notifications": len([n for n in self._notifications if not n["delivered"]]),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_runner: HeartbeatRunner | None = None


def get_heartbeat_runner() -> HeartbeatRunner:
    global _runner
    if _runner is None:
        _runner = HeartbeatRunner()
    return _runner
