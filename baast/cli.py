import asyncio
import logging
import importlib

import uvicorn

# from apscheduler.schedulers.async_ import AsyncScheduler
# from apscheduler.triggers.interval import IntervalTrigger

from baast.baast import Baast

from loguru import logger

def client():
    asgi_module, application_path = "baast.asgi:application".split(':', 1)
    application_module = importlib.import_module(asgi_module)
    for part in application_path.split('.'):
        application = getattr(application_module, part)
        
    client = Baast(application, '3.0.0')
    client.run()

def http():
    uvicorn.run("baast.asgi:application")


async def main():
    # async with AsyncScheduler( identity="Baast" ) as scheduler:
    #     #self.scheduler.event_broker.subscribe(listener)
    #     await scheduler.add_job(http)
    #     #await scheduler.add_job(client)


    #     await scheduler.start_in_background()
    #     await scheduler.wait_until_stopped()
    await asyncio.to_thread(http)
    await asyncio.to_thread(client)


    
try:
    loop = asyncio.get_running_loop()
except RuntimeError:  # 'RuntimeError: There is no current event loop...'
    loop = None
    
if loop and loop.is_running():
    print('Async event loop already running. Adding coroutine to the event loop.')
    tsk = loop.create_task(main())
    # ^-- https://docs.python.org/3/library/asyncio-task.html#task-object
    # Optionally, a callback function can be executed when the coroutine completes
    tsk.add_done_callback(
        lambda t: print(f'Task done with result={t.result()}  << return val of main()'))
else:
    print('Starting new event loop')
    result = asyncio.run(main())
    


#if __name__ == "__main__":
    #asyncio.run(main())
    #asyncio.run(main.run_tasks())
    
    # asyncio.create_task(http())
    # asyncio.create_task(client())
    # asyncio.ensure_future(client())

