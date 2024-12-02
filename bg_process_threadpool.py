import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from queue import Empty, Queue
from typing import Dict

from aiohttp import ClientSession

# Logger setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# Enum for task states
class TaskManagerState(Enum):
    Pending = "pending"
    Generating = "generating"
    Finished = "finished"
    Failed = "failed"


class BackgroundManager:
    MAX_CONCURRENT_WORKERS = 5
    QUEUE_TIMEOUT = 1  # Time in seconds before checking queue again

    def __init__(self):
        self._queue: Queue[TaskManager] = Queue()
        self._shutdown_event = asyncio.Event()
        self._executor = ThreadPoolExecutor(
            max_workers=BackgroundManager.MAX_CONCURRENT_WORKERS
        )

    def start_background_processing(self, data: Dict, **kwargs):
        """Add task to queue for background processing."""
        task_manager = TaskManager(data, **kwargs)
        self._queue.put(task_manager)

    def start(self):
        """Start background workers to process tasks in the queue."""
        logger.info(
            f"Starting {BackgroundManager.MAX_CONCURRENT_WORKERS} worker threads."
        )
        for _ in range(BackgroundManager.MAX_CONCURRENT_WORKERS):
            self._executor.submit(self._process)

    def stop(self):
        """Gracefully stop the worker threads."""
        logger.info("Stopping workers.")
        self._shutdown_event.set()
        self._executor.shutdown(wait=True)

    def _process(self):
        """Process tasks from the queue in worker threads based on their status."""
        while not self._shutdown_event.is_set():
            try:
                task_manager = self._queue.get(timeout=BackgroundManager.QUEUE_TIMEOUT)
                if task_manager and task_manager.state == TaskManagerState.Pending:
                    logger.info(f"Processing task: {task_manager._data}")
                    task_manager.process()
                    self._queue.task_done()
                else:
                    # Skip processing if the task is not in 'Pending' state
                    logger.info(
                        f"Skipping task {task_manager._data} as it is already {task_manager.state.value}"
                    )
            except Empty:
                time.sleep(0.1)
                continue
            except Exception as e:
                logger.error(f"Error processing task: {str(e)}")


class TaskManager:
    def __init__(self, data: Dict, **kwargs):
        self._data = data
        self.state = TaskManagerState.Pending
        self._session: ClientSession = None

    def process(self):
        """Process the task asynchronously within the thread."""
        self.state = TaskManagerState.Generating
        try:
            # Run async tasks within the thread using asyncio event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)  # Setting a new event loop for this thread
            loop.run_until_complete(self._process())
            self.state = TaskManagerState.Finished
        except Exception as e:
            self.state = TaskManagerState.Failed
            logger.error(f"Error processing task: {str(e)}")
        finally:
            loop.close()

    async def _process(self):
        """Perform the actual async tasks."""
        try:
            async with ClientSession() as session:
                self._session = session
                await self._initial_task(session)
                await asyncio.gather(
                    self._generate_first_task(session),
                    # Additional tasks can be added here
                )
            await self.finalize()
        except Exception as e:
            logger.error(f"Failed during task processing: {str(e)}")
            raise

    async def _initial_task(self, session: ClientSession):
        """Perform the initial task for the data."""
        self._data["data"] = {}

    async def _generate_first_task(self, session: ClientSession):
        """Simulate a data generation task."""
        self._data["data"]["first"] = "test_data"

    async def finalize(self):
        """Finalize the task processing."""
        logger.info(f"Task completed: {self._data}")
        # Placeholder for actual processing like DB update, logging, etc.


# Example Usage
if __name__ == "__main__":
    background_manager = BackgroundManager()
    background_manager.start()

    # Add tasks to the queue
    for i in range(10):
        background_manager.start_background_processing({"task_id": i})

    print("Background processing started.")

    # Optionally, stop the manager after some time or upon application shutdown
    time.sleep(10)  # Simulate runtime
    background_manager.stop()
