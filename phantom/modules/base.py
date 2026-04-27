"""
PhantomStrike Base Module — Abstract base for all offensive modules.
Every module (OSINT, Network, Web, Cloud, etc.) inherits from this.
"""
from __future__ import annotations
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from phantom.core.events import EventBus, Event, EventType


class ModuleStatus(str, Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ModuleResult:
    """Standardized result from any module operation."""
    module_name: str
    operation: str
    success: bool
    data: Any = None
    errors: list[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    findings_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class BaseModule(ABC):
    """
    Abstract base class for all PhantomStrike offensive modules.
    Provides: event bus integration, multi-threading, lifecycle management.
    """

    def __init__(self, event_bus: EventBus, config: dict = None):
        self.event_bus = event_bus
        self.config = config or {}
        self.status = ModuleStatus.IDLE
        self.logger = logging.getLogger(f"phantom.{self.name}")
        self._results: list[ModuleResult] = []
        self._tasks: list[asyncio.Task] = []
        self._semaphore: Optional[asyncio.Semaphore] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique module identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Module description."""
        ...

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def category(self) -> str:
        return "general"

    async def initialize(self, max_concurrent: int = 50):
        """Initialize module resources."""
        self.status = ModuleStatus.INITIALIZING
        self._semaphore = asyncio.Semaphore(max_concurrent)
        await self._setup()
        self.status = ModuleStatus.IDLE
        await self.event_bus.emit(Event(
            type=EventType.MODULE_LOADED,
            data={"module": self.name, "version": self.version},
            source=self.name,
        ))
        self.logger.info(f"Module '{self.name}' initialized")

    @abstractmethod
    async def _setup(self):
        """Module-specific setup (override in subclass)."""
        ...

    @abstractmethod
    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Execute the module's primary operation."""
        ...

    async def run_threaded(self, targets: list[str], options: dict = None) -> list[ModuleResult]:
        """Run module against multiple targets using multi-threading."""
        self.status = ModuleStatus.RUNNING
        options = options or {}

        async def _run_one(target: str) -> ModuleResult:
            async with self._semaphore:
                try:
                    return await self.run(target, options)
                except Exception as e:
                    self.logger.error(f"Error on target {target}: {e}")
                    return ModuleResult(
                        module_name=self.name, operation="run",
                        success=False, errors=[str(e)],
                    )

        tasks = [asyncio.create_task(_run_one(t)) for t in targets]
        self._tasks = tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final = []
        for r in results:
            if isinstance(r, Exception):
                final.append(ModuleResult(
                    module_name=self.name, operation="run",
                    success=False, errors=[str(r)],
                ))
            else:
                final.append(r)

        self._results.extend(final)
        self.status = ModuleStatus.COMPLETED
        return final

    async def cleanup(self):
        """Cleanup module resources."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self.status = ModuleStatus.IDLE

    def get_results(self) -> list[ModuleResult]:
        return self._results.copy()

    def get_findings_count(self) -> int:
        return sum(r.findings_count for r in self._results)

    def __repr__(self) -> str:
        return f"<Module:{self.name} status={self.status.value}>"
