# import asyncio

# # Shared resource
# counter = 0

# # Async lock to synchronize access
# lock = asyncio.Lock()


# async def increment():
#     global counter
#     async with lock:  # Acquiring the lock asynchronously
#         current = counter
#         await asyncio.sleep(0.1)  # Simulate async work
#         counter = current + 1
#         print(f"Counter incremented to {counter}")


# # Main function to run the tasks
# async def main():
#     tasks = []
#     for _ in range(5):
#         task = asyncio.create_task(increment())
#         tasks.append(task)

#     await asyncio.gather(*tasks)


# # Run the asyncio event loop
# asyncio.run(main())


# import threading

# # Create an RLock
# rlock = threading.RLock()


# def recursive_task(n):
#     # with rlock:
#     if n > 0:
#         print(f"Task {n} started")
#         recursive_task(n - 1)  # Re-entering the same lock
#         print(f"Task {n} finished")


# thread = threading.Thread(target=recursive_task, args=(5,))
# thread.start()
# thread.join()


import threading
import time

# Create a semaphore with 3 available slots
semaphore = threading.Semaphore(3)

n = 1


def task(id):
    print(f"Task {id}")
    with semaphore:  # Acquiring a permit
        global n
        print(f"Task {id} started {n}")
        time.sleep(2)  # Simulate some work
        n += 1
        print(f"Task {id} finished")


threads = []
for i in range(6):
    t = threading.Thread(target=task, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
