import asyncio
import logging
from aiohttp import ClientSession, ClientTimeout
from enum import Enum
import random

# Setting up logging
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

    async def start_background_processing(self, data, **kwargs):
        # Add the task to the queue for processing
        task_manager = TaskManager(data, **kwargs)
        await self._queue.put(task_manager)

    async def start(self):
        # Start processing tasks concurrently
        await self._process()

    async def _process(self):
        while not self._shutdown_event.is_set():
            # Assign workers if there are available tasks and space for more workers
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

            # Remove finished or failed workers
            self._workers -= finished_tasks

            # Avoid busy-waiting by sleeping for a short interval
            await asyncio.sleep(0.1)

    async def _process_task(self, task_manager: TaskManager):
        try:
            await task_manager.process()
        except Exception as e:
            logger.error(f"Task processing failed: {e}")
        finally:
            self._workers.remove(task_manager)

    async def stop(self):
        # Trigger graceful shutdown
        self._shutdown_event.set()
        # Wait until all tasks are completed or failed
        while self._workers:
            await asyncio.sleep(0.1)
        logger.info("All tasks have been processed and background manager is stopped.")


class TaskManager:
    def __init__(self, data):
        self._data = data
        self.state = TaskManagerState.Pending
        self._session: ClientSession = None
        self.retry_count = 0

    async def process(self):
        try:
            async with ClientSession(
                timeout=ClientTimeout(total=BackgroundManager.TASK_TIMEOUT)
            ) as session:
                self._session = session
                await self._initial_task(session)

                # Simulate multiple concurrent tasks (can be expanded)
                await asyncio.gather(
                    self._generate_first_task(session),
                    self._generate_second_task(session),
                )
            self.state = TaskManagerState.Finished
        except Exception as e:
            self.state = TaskManagerState.Failed
            logger.error(f"Error processing task: {e}")
            await self._handle_failure(e)

    async def _initial_task(self, session: ClientSession):
        # Simulate an initial task processing (e.g., DB or API call)
        logger.info("Starting initial task")
        self._data["data"] = {}

    async def _generate_first_task(self, session: ClientSession):
        # Simulate the first data generation task (e.g., external API call)
        logger.info("Generating first task")
        self._data["data"]["first"] = f"test_data_{random.randint(1000, 9999)}"

    async def _generate_second_task(self, session: ClientSession):
        # Simulate the second data generation task
        logger.info("Generating second task")
        self._data["data"]["second"] = f"extra_data_{random.randint(1000, 9999)}"

    async def _handle_failure(self, error):
        if self.retry_count < BackgroundManager.RETRY_LIMIT:
            self.retry_count += 1
            logger.info(
                f"Retrying task (attempt {self.retry_count}/{BackgroundManager.RETRY_LIMIT}) due to error: {error}"
            )
            await asyncio.sleep(2**self.retry_count)  # Exponential backoff
            await self.process()  # Retry the task
        else:
            logger.error("Max retry limit reached, task failed permanently.")

    async def finalize(self):
        # Log or process data after task completion (e.g., DB update)
        if self.state == TaskManagerState.Finished:
            logger.info(f"Task completed: {self._data}")
        else:
            logger.error(f"Task failed: {self._data}")
        print(self._data)  # Placeholder for actual processing like DB update


async def main():
    manager = BackgroundManager()

    # Add tasks to the manager (example task data)
    for i in range(10):
        data = {"id": i, "data": {"name": f"Task {i}"}}
        await manager.start_background_processing(data)

    # Start processing tasks in the background
    await manager.start()

    # Optionally, stop the manager after some time or upon application shutdown
    await asyncio.sleep(10)  # Simulate runtime
    await manager.stop()


# Run the main function in the event loop
asyncio.run(main())
