"""
PhantomStrike Event Bus — Async pub/sub system for inter-module communication.
Every module talks through the event bus, enabling real-time data flow.
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine
from collections import defaultdict

logger = logging.getLogger("phantom.events")


class EventType(str, Enum):
    # === Lifecycle ===
    ENGINE_START = "engine.start"
    ENGINE_STOP = "engine.stop"
    MODULE_LOADED = "module.loaded"
    MODULE_ERROR = "module.error"

    # === Reconnaissance ===
    TARGET_ADDED = "target.added"
    SUBDOMAIN_FOUND = "recon.subdomain"
    PORT_FOUND = "recon.port"
    SERVICE_DETECTED = "recon.service"
    TECH_DETECTED = "recon.technology"
    EMAIL_FOUND = "recon.email"
    ENDPOINT_FOUND = "recon.endpoint"

    # === Vulnerability ===
    VULN_FOUND = "vuln.found"
    VULN_CONFIRMED = "vuln.confirmed"
    VULN_EXPLOITED = "vuln.exploited"

    # === Attack Chain ===
    ATTACK_PLANNED = "attack.planned"
    ATTACK_STARTED = "attack.started"
    ATTACK_PROGRESS = "attack.progress"
    ATTACK_COMPLETED = "attack.completed"

    # === Credential ===
    CRED_FOUND = "cred.found"
    HASH_CRACKED = "cred.cracked"
    SESSION_CAPTURED = "cred.session"

    # === AI ===
    AI_ANALYSIS = "ai.analysis"
    AI_PAYLOAD = "ai.payload"
    AI_CHAIN = "ai.chain"
    AI_PROVIDER_SWITCH = "ai.provider_switch"

    # === Browser (Playwright) ===
    BROWSER_STARTED = "browser.started"
    BROWSER_PAGE_LOADED = "browser.page_loaded"
    BROWSER_XSS_FOUND = "browser.xss"
    BROWSER_COOKIE_CAPTURED = "browser.cookie"
    BROWSER_SCREENSHOT = "browser.screenshot"

    # === Reporting ===
    REPORT_GENERATED = "report.generated"


@dataclass
class Event:
    """An event in the PhantomStrike event system."""
    type: EventType
    data: Any = None
    source: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)
    severity: str = "info"
    metadata: dict = field(default_factory=dict)

    def __str__(self):
        return f"[{self.timestamp:%H:%M:%S}] [{self.source}] {self.type.value}: {self.data}"


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    High-performance async event bus with multi-threading support.
    Enables all modules to communicate in real-time.
    """

    def __init__(self, max_queue_size: int = 10000):
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._history: list[Event] = []
        self._max_history: int = 5000
        self._running = False
        self._processor_task: asyncio.Task | None = None
        self._stats: dict[str, int] = defaultdict(int)

    def subscribe(self, event_type: EventType, handler: EventHandler):
        """Subscribe to a specific event type."""
        self._handlers[event_type].append(handler)
        logger.debug(f"[EventBus] Handler subscribed to {event_type.value}")

    def subscribe_all(self, handler: EventHandler):
        """Subscribe to ALL events (for logging, UI updates, etc.)."""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        """Unsubscribe from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def emit(self, event: Event):
        """Emit an event — non-blocking, queued for processing."""
        await self._queue.put(event)
        self._stats[event.type.value] += 1

    async def emit_nowait(self, event: Event):
        """Emit without waiting — drops if queue is full."""
        try:
            self._queue.put_nowait(event)
            self._stats[event.type.value] += 1
        except asyncio.QueueFull:
            logger.warning("[EventBus] Queue full, event dropped")

    async def start(self):
        """Start the event processor loop."""
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("[EventBus] Started")

    async def stop(self):
        """Stop the event processor."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info(f"[EventBus] Stopped. Total events: {sum(self._stats.values())}")

    async def _process_events(self):
        """Main event processing loop — dispatches events to handlers."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Store in history
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            # Dispatch to specific handlers
            handlers = self._handlers.get(event.type, []) + self._global_handlers
            tasks = [asyncio.create_task(h(event)) for h in handlers]
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        logger.error(f"[EventBus] Handler error: {r}")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def get_history(self, event_type: EventType | None = None, limit: int = 50) -> list[Event]:
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]
