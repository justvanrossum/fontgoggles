import asyncio
import functools
import logging


def asyncTask(func):
    """Wraps an async function or method into a regular function, that
    will schedule the async function as a task. Returns an asyncio Task
    object, that can be cancelled.
    """
    @functools.wraps(func)
    def createFuncTask(*args, **kwargs):
        coro = func(*args, **kwargs)
        task = asyncio.create_task(coro)
        task.add_done_callback(_done_callback)
        return task
    return createFuncTask


def asyncTaskAutoCancel(func):
    """Wraps an async method into a regular method, that will schedule
    the async function as a task. If this task has previously been scheduled
    and has not yet run, it will be cancelled. So a newly scheduled task
    overrides an older one.
    """
    taskAttributeName = f"_{func.__name__}_autoCancelTask"
    @functools.wraps(func)
    def createFuncTask(self, *args, **kwargs):
        oldTask = getattr(self, taskAttributeName, None)
        if oldTask is not None:
            oldTask.cancel()
        coro = func(self, *args, **kwargs)
        task = asyncio.create_task(coro)
        task.add_done_callback(_done_callback)
        setattr(self, taskAttributeName, task)
        return task
    return createFuncTask


def _done_callback(task):
    if task.cancelled():
        return
    if task.exception() is not None:
        task.print_stack()


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
        except Exception:
            logging.exception(func.__name__)

    return wrapper
