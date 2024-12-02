import asyncio
import logging
from aiohttp import ClientSession, ClientTimeout
from concurrent.futures import ProcessPoolExecutor
from enum import Enum
import random
import time
import os

# Logger setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class TaskManagerState(Enum):
    Pending = "pending"
    Generating = "generating"
    Finished = "finished"
    Failed = "failed"


class BackgroundManager:
    MAX_CONCURRENT_WORKERS = 5
    RETRY_LIMIT = 3  # Max number of retries on failure
    TASK_TIMEOUT = 30  # Timeout for each task in seconds

    def __init__(self):
        self._queue: asyncio.Queue[TaskManager] = asyncio.Queue()
        self._workers: set[TaskManager] = set()
        self._shutdown_event = asyncio.Event()
        self._executor = ProcessPoolExecutor(
            max_workers=5
        )  # CPU-bound tasks handled by separate processes

    async def start_background_processing(self, data, **kwargs):
        """Add task to the queue for processing."""
        task_manager = TaskManager(data, self._executor, **kwargs)
        await self._queue.put(task_manager)

    async def start(self):
        """Start the task processing."""
        await self._process()

    async def _process(self):
        """Process tasks from the queue using a limited number of workers."""
        while not self._shutdown_event.is_set():
            if (
                len(self._workers) < BackgroundManager.MAX_CONCURRENT_WORKERS
                and not self._queue.empty()
            ):
                task_manager = await self._queue.get()
                self._workers.add(task_manager)
                asyncio.create_task(self._process_task(task_manager))

            # Clean up finished or failed tasks
            finished_tasks = {
                task
                for task in self._workers
                if task.state in {TaskManagerState.Finished, TaskManagerState.Failed}
            }
            await asyncio.gather(*(task.finalize() for task in finished_tasks))
            self._workers -= finished_tasks

            await asyncio.sleep(0.1)  # Avoid busy-waiting

    async def _process_task(self, task_manager: "TaskManager"):
        try:
            await task_manager.process()
        except Exception as e:
            logger.error(f"Task processing failed: {e}")
        finally:
            self._workers.remove(task_manager)

    async def stop(self):
        """Gracefully shut down by waiting for all tasks to finish."""
        self._shutdown_event.set()
        while self._workers:
            await asyncio.sleep(0.1)
        logger.info("All tasks have been processed and background manager is stopped.")


class TaskManager:
    def __init__(self, data, executor: ProcessPoolExecutor, **kwargs):
        self._data = data
        self.state = TaskManagerState.Pending
        self.retry_count = 0
        self._executor = executor

    async def process(self):
        """Process the task with retries and backoff."""
        try:
            async with ClientSession(
                timeout=ClientTimeout(total=BackgroundManager.TASK_TIMEOUT)
            ) as session:
                # Start I/O-bound tasks concurrently
                await self._initial_task(session)
                task1 = asyncio.create_task(self._generate_first_task(session))
                task2 = asyncio.create_task(self._generate_second_task(session))

                # Wait for both I/O-bound tasks to complete
                await asyncio.gather(task1, task2)

            # Handle CPU-bound task
            await self._handle_cpu_task()

            self.state = TaskManagerState.Finished
        except Exception as e:
            self.state = TaskManagerState.Failed
            logger.error(f"Error processing task: {e}")
            await self._handle_failure(e)

    async def _initial_task(self, session: ClientSession):
        """Simulate an initial IO-bound task."""
        self._data["data"] = {}

    async def _generate_first_task(self, session: ClientSession):
        """Simulate an IO-bound task (e.g., HTTP request)."""
        await asyncio.sleep(1)  # Simulating network delay
        self._data["data"]["first"] = f"test_data_{random.randint(1000, 9999)}"

    async def _generate_second_task(self, session: ClientSession):
        """Simulate another IO-bound task."""
        await asyncio.sleep(1)  # Simulating another network delay
        self._data["data"]["second"] = f"extra_data_{random.randint(1000, 9999)}"

    async def _handle_cpu_task(self):
        """Handle CPU-intensive task in a separate process using the executor."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._cpu_bound_task)
        self._data["data"]["cpu_result"] = result

    def _cpu_bound_task(self):
        """Simulate a CPU-intensive task (e.g., a complex calculation)."""
        logger.info(f"Running CPU-intensive task in process {os.getpid()}")
        time.sleep(3)  # Simulating CPU-bound work
        return random.randint(10000, 99999)

    async def _handle_failure(self, error):
        """Handle task failure with retries and exponential backoff."""
        if self.retry_count < BackgroundManager.RETRY_LIMIT:
            self.retry_count += 1
            logger.info(
                f"Retrying task ({self.retry_count}/{BackgroundManager.RETRY_LIMIT}) due to error: {error}"
            )
            await asyncio.sleep(2**self.retry_count)  # Exponential backoff
            await self.process()  # Retry the task
        else:
            logger.error("Max retry limit reached, task failed permanently.")

    async def finalize(self):
        """Finalize task processing."""
        if self.state == TaskManagerState.Finished:
            logger.info(f"Task completed: {self._data}")
        else:
            logger.error(f"Task failed: {self._data}")
        print(self._data)  # Placeholder for actual processing like DB update


# Example usage
async def main():
    manager = BackgroundManager()

    # Add tasks to the manager
    for i in range(10):
        data = {"id": i, "data": {"name": f"Task {i}"}}
        await manager.start_background_processing(data)

    # Start processing tasks
    await manager.start()

    # Optionally, stop the manager after some time or upon application shutdown
    await asyncio.sleep(10)  # Simulate runtime
    await manager.stop()


# Run the main function
asyncio.run(main())
