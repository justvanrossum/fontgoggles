import asyncio
import concurrent.futures


_threadPool = None
_processPool = None


def _getThreadPool():
    global _threadPool
    if _threadPool is None:
        _threadPool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    return _threadPool


def _getProcessPool():
    global _processPool
    if _processPool is None:
        _processPool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    return _processPool


async def runInThreadPool(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_getThreadPool(), func, *args, **kwargs)
    return await future


async def runInProcessPool(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_getProcessPool(), func, *args, **kwargs)
    return await future
