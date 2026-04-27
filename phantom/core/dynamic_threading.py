"""
Dynamic Thread Pool Manager for PhantomStrike
Provides 200+ threads with auto-scaling based on system load and target response
"""

import asyncio
import psutil
import time
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)


@dataclass
class ThreadPoolMetrics:
    """Metrics for thread pool performance."""
    active_threads: int
    queued_tasks: int
    completed_tasks: int
    failed_tasks: int
    avg_task_duration: float
    cpu_percent: float
    memory_percent: float
    target_response_time: float
    timestamp: float


class DynamicThreadPool:
    """
    Dynamic thread pool that auto-scales based on:
    - System resources (CPU, memory)
    - Target response times
    - Task queue depth
    """
    
    # Scaling limits
    MIN_THREADS = 20
    MAX_THREADS = 300  # Can go up to 300 for aggressive mode
    DEFAULT_THREADS = 100
    
    # Scaling thresholds
    CPU_HIGH_THRESHOLD = 80  # Scale down if CPU > 80%
    CPU_LOW_THRESHOLD = 40  # Scale up if CPU < 40%
    MEMORY_HIGH_THRESHOLD = 85  # Scale down if memory > 85%
    QUEUE_HIGH_THRESHOLD = 50  # Scale up if queue > 50 tasks
    TARGET_SLOW_THRESHOLD = 5.0  # Scale down if target responds slowly (>5s)
    
    def __init__(self, 
                 initial_threads: int = 100,
                 max_threads: int = 200,
                 min_threads: int = 20,
                 scaling_interval: float = 5.0):
        self.initial_threads = initial_threads
        self.max_threads = max_threads
        self.min_threads = min_threads
        self.scaling_interval = scaling_interval
        
        self._current_threads = initial_threads
        self._executor: Optional[ThreadPoolExecutor] = None
        self._metrics_history: List[ThreadPoolMetrics] = []
        self._task_durations: List[float] = []
        self._scaling_enabled = True
        self._scaling_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Callbacks
        self._on_scale_callbacks: List[Callable] = []
        
    async def start(self):
        """Start the dynamic thread pool."""
        self._executor = ThreadPoolExecutor(
            max_workers=self._current_threads,
            thread_name_prefix="phantom_worker"
        )
        
        if self._scaling_enabled:
            self._scaling_task = asyncio.create_task(self._scaling_loop())
            
        logger.info(f"[THREADS] Dynamic pool started with {self._current_threads} threads")
        logger.info(f"[THREADS] Limits: min={self.min_threads}, max={self.max_threads}")
        
    async def stop(self):
        """Stop the thread pool."""
        if self._scaling_task:
            self._scaling_task.cancel()
            try:
                await self._scaling_task
            except asyncio.CancelledError:
                pass
                
        if self._executor:
            self._executor.shutdown(wait=True)
            
        logger.info("[THREADS] Dynamic pool stopped")
        
    async def submit(self, fn, *args, **kwargs):
        """Submit a task to the pool."""
        if not self._executor:
            raise RuntimeError("Thread pool not started")
            
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(
                self._executor, 
                self._wrap_task(fn, start_time), 
                *args, 
                **kwargs
            )
            return await future
        except Exception as e:
            logger.error(f"[THREADS] Task failed: {e}")
            raise
            
    def _wrap_task(self, fn, start_time: float):
        """Wrap task to track duration."""
        def wrapper(*args, **kwargs):
            try:
                result = fn(*args, **kwargs)
                duration = time.time() - start_time
                self._task_durations.append(duration)
                # Keep only last 100 durations
                if len(self._task_durations) > 100:
                    self._task_durations.pop(0)
                return result
            except Exception as e:
                logger.error(f"[THREADS] Task error: {e}")
                raise
        return wrapper
        
    async def _scaling_loop(self):
        """Background loop for dynamic scaling."""
        while True:
            try:
                await asyncio.sleep(self.scaling_interval)
                await self._evaluate_and_scale()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[THREADS] Scaling error: {e}")
                
    async def _evaluate_and_scale(self):
        """Evaluate metrics and scale thread pool."""
        metrics = await self._collect_metrics()
        self._metrics_history.append(metrics)
        
        # Keep only last 10 metrics
        if len(self._metrics_history) > 10:
            self._metrics_history.pop(0)
            
        # Decide scaling action
        action = self._decide_scaling(metrics)
        
        if action != 0:
            async with self._lock:
                new_count = self._current_threads + action
                new_count = max(self.min_threads, min(self.max_threads, new_count))
                
                if new_count != self._current_threads:
                    await self._resize_pool(new_count)
                    
    def _decide_scaling(self, metrics: ThreadPoolMetrics) -> int:
        """
        Decide whether to scale up, down, or stay.
        Returns: positive (scale up), negative (scale down), 0 (no change)
        """
        # Emergency scale down
        if metrics.cpu_percent > 90 or metrics.memory_percent > 90:
            logger.warning(f"[THREADS] Emergency scale down! CPU={metrics.cpu_percent}%, MEM={metrics.memory_percent}%")
            return -50
            
        # Scale down conditions
        if metrics.cpu_percent > self.CPU_HIGH_THRESHOLD:
            return -20
        if metrics.memory_percent > self.MEMORY_HIGH_THRESHOLD:
            return -20
        if metrics.target_response_time > self.TARGET_SLOW_THRESHOLD:
            return -10
            
        # Scale up conditions
        if metrics.cpu_percent < self.CPU_LOW_THRESHOLD and metrics.queued_tasks > self.QUEUE_HIGH_THRESHOLD:
            return 30
        if metrics.queued_tasks > self.QUEUE_HIGH_THRESHOLD * 2:
            return 50
        if metrics.avg_task_duration < 0.5 and metrics.cpu_percent < 60:  # Fast tasks, low CPU
            return 20
            
        return 0
        
    async def _collect_metrics(self) -> ThreadPoolMetrics:
        """Collect current system and pool metrics."""
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory().percent
        
        # Calculate average task duration
        avg_duration = 0.0
        if self._task_durations:
            avg_duration = sum(self._task_durations) / len(self._task_durations)
            
        return ThreadPoolMetrics(
            active_threads=self._current_threads,
            queued_tasks=self._get_queue_depth(),
            completed_tasks=len(self._task_durations),
            failed_tasks=0,  # Would track from error handler
            avg_task_duration=avg_duration,
            cpu_percent=cpu,
            memory_percent=memory,
            target_response_time=avg_duration,
            timestamp=time.time()
        )
        
    def _get_queue_depth(self) -> int:
        """Get approximate queue depth."""
        # ThreadPoolExecutor doesn't expose queue depth directly
        # We estimate based on completed vs submitted
        return max(0, len(self._task_durations) - self._current_threads)
        
    async def _resize_pool(self, new_size: int):
        """Resize the thread pool."""
        logger.info(f"[THREADS] Resizing pool: {self._current_threads} -> {new_size}")
        
        # Create new executor
        new_executor = ThreadPoolExecutor(
            max_workers=new_size,
            thread_name_prefix="phantom_worker"
        )
        
        # Shutdown old executor (let running tasks complete)
        old_executor = self._executor
        self._executor = new_executor
        self._current_threads = new_size
        
        # Shutdown old in background
        asyncio.create_task(self._shutdown_old_executor(old_executor))
        
        # Notify callbacks
        for callback in self._on_scale_callbacks:
            try:
                callback(self._current_threads)
            except:
                pass
                
    async def _shutdown_old_executor(self, executor: ThreadPoolExecutor):
        """Shutdown old executor gracefully."""
        executor.shutdown(wait=True)
        
    def get_metrics(self) -> ThreadPoolMetrics:
        """Get current metrics."""
        if self._metrics_history:
            return self._metrics_history[-1]
        return ThreadPoolMetrics(
            active_threads=self._current_threads,
            queued_tasks=0,
            completed_tasks=0,
            failed_tasks=0,
            avg_task_duration=0.0,
            cpu_percent=0.0,
            memory_percent=0.0,
            target_response_time=0.0,
            timestamp=time.time()
        )
        
    def on_scale(self, callback: Callable):
        """Register callback for scaling events."""
        self._on_scale_callbacks.append(callback)
        
    def set_thread_count(self, count: int):
        """Manually set thread count (disables auto-scaling)."""
        self._scaling_enabled = False
        count = max(self.min_threads, min(self.max_threads, count))
        asyncio.create_task(self._resize_pool(count))


class AdaptiveSemaphore:
    """
    Semaphore that adapts its value based on target responsiveness.
    Used for controlling concurrent connections to avoid overwhelming targets.
    """
    
    def __init__(self, initial_value: int = 50, min_value: int = 10, max_value: int = 200):
        self.min_value = min_value
        self.max_value = max_value
        self._current_value = initial_value
        self._semaphore = asyncio.Semaphore(initial_value)
        self._response_times: List[float] = []
        
    async def acquire(self):
        """Acquire semaphore."""
        await self._semaphore.acquire()
        
    def release(self):
        """Release semaphore."""
        self._semaphore.release()
        
    def report_response_time(self, duration: float):
        """Report a response time for adaptation."""
        self._response_times.append(duration)
        if len(self._response_times) > 50:
            self._response_times.pop(0)
            self._adapt()
            
    def _adapt(self):
        """Adapt semaphore size based on response times."""
        if not self._response_times:
            return
            
        avg_response = sum(self._response_times) / len(self._response_times)
        
        # If target is slow, reduce concurrency
        if avg_response > 3.0:  # > 3 seconds
            new_value = max(self.min_value, self._current_value - 10)
        # If target is fast, increase concurrency
        elif avg_response < 0.5:  # < 0.5 seconds
            new_value = min(self.max_value, self._current_value + 10)
        else:
            return
            
        if new_value != self._current_value:
            self._current_value = new_value
            # Create new semaphore with new value
            self._semaphore = asyncio.Semaphore(new_value)
            logger.info(f"[ADAPTIVE] Semaphore adjusted to {new_value} (avg response: {avg_response:.2f}s)")
            
    async def __aenter__(self):
        await self.acquire()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
