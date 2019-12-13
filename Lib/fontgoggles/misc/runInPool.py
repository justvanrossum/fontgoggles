import asyncio
import concurrent.futures


_threadPool = concurrent.futures.ThreadPoolExecutor(max_workers=5)

async def runInThreadPool(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_threadPool, func, *args, **kwargs)
    return await future


_processPool = concurrent.futures.ProcessPoolExecutor()

async def runInProcessPool(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_processPool, func, *args, **kwargs)
    return await future
