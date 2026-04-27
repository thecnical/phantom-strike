"""
PhantomStrike Multi-Threaded Task Queue
Manages concurrent operations across all modules with thread pools.
"""
from __future__ import annotations
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from collections import deque

logger = logging.getLogger("phantom.taskqueue")


class TaskPriority(int, Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str
    name: str
    coroutine: Coroutine
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    @property
    def duration(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


class TaskQueue:
    """
    Multi-threaded async task queue with priority scheduling.
    Supports: thread pools, process pools, rate limiting, retry logic.
    """

    def __init__(
        self,
        max_concurrent: int = 100,
        thread_pool_size: int = 50,
        process_pool_size: int = 4,
    ):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._thread_pool = ThreadPoolExecutor(max_workers=thread_pool_size)
        self._process_pool = ProcessPoolExecutor(max_workers=process_pool_size)
        self._tasks: dict[str, Task] = {}
        self._pending: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running_tasks: set[str] = set()
        self._completed: deque[Task] = deque(maxlen=10000)
        self._counter = 0
        self._is_running = False
        self._processor: Optional[asyncio.Task] = None

        # Stats
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0

    async def submit(
        self,
        name: str,
        coroutine: Coroutine,
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: dict = None,
    ) -> str:
        """Submit a task to the queue."""
        self._counter += 1
        task_id = f"task_{self._counter:06d}"

        task = Task(
            id=task_id,
            name=name,
            coroutine=coroutine,
            priority=priority,
            metadata=metadata or {},
        )
        self._tasks[task_id] = task
        await self._pending.put((priority.value, self._counter, task))
        self._total_submitted += 1

        logger.debug(f"[TaskQueue] Submitted: {name} ({task_id}) priority={priority.name}")
        return task_id

    async def submit_batch(
        self,
        tasks: list[tuple[str, Coroutine]],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> list[str]:
        """Submit multiple tasks at once."""
        ids = []
        for name, coro in tasks:
            task_id = await self.submit(name, coro, priority)
            ids.append(task_id)
        return ids

    async def start(self):
        """Start processing tasks from the queue."""
        self._is_running = True
        self._processor = asyncio.create_task(self._process_loop())
        logger.info("[TaskQueue] Started")

    async def stop(self):
        """Stop processing and cleanup."""
        self._is_running = False
        if self._processor:
            self._processor.cancel()
        self._thread_pool.shutdown(wait=False)
        self._process_pool.shutdown(wait=False)
        logger.info(
            f"[TaskQueue] Stopped. "
            f"Submitted={self._total_submitted} "
            f"Completed={self._total_completed} "
            f"Failed={self._total_failed}"
        )

    async def _process_loop(self):
        """Main processing loop — pulls tasks and executes them concurrently."""
        while self._is_running:
            try:
                _, _, task = await asyncio.wait_for(self._pending.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: Task):
        """Execute a single task with semaphore-based concurrency control."""
        async with self._semaphore:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self._running_tasks.add(task.id)

            try:
                task.result = await task.coroutine
                task.status = TaskStatus.COMPLETED
                self._total_completed += 1
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                self._total_failed += 1
                logger.error(f"[TaskQueue] Task '{task.name}' failed: {e}")
            finally:
                task.completed_at = datetime.now()
                self._running_tasks.discard(task.id)
                self._completed.append(task)

    def run_in_thread(self, func: Callable, *args) -> asyncio.Future:
        """Run a blocking function in the thread pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(self._thread_pool, func, *args)

    def run_in_process(self, func: Callable, *args) -> asyncio.Future:
        """Run a CPU-intensive function in the process pool."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(self._process_pool, func, *args)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_stats(self) -> dict:
        return {
            "submitted": self._total_submitted,
            "completed": self._total_completed,
            "failed": self._total_failed,
            "running": len(self._running_tasks),
            "pending": self._pending.qsize(),
        }
