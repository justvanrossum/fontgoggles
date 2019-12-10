import asyncio
import functools
import logging


def asyncTask(func):
    """Wraps an async function or method into a regular function, that
    will schedule the async function as a task. Returns an asyncio Task
    object, that can be cancelled.
    """
    @functools.wraps(func)
    def createFuncTask(*args):
        coro = func(*args)
        return asyncio.create_task(coro)
    return createFuncTask


def suppressAndLogException(func):
    """Wraps a method or function into a try/except, logging any errors while
    silencing them. This is handy for debugging Cocoa methods, which often
    cause trouble if they trow an exception.

    When an exception occurs, the decorated function will return None, so only
    use this decorator if returning None is a valid option.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            logging.exception(func.__name__)
    return wrapper
