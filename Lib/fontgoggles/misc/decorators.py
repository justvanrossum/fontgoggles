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
        return asyncio.create_task(coro)
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
        def _done_callback(task):
            if task.cancelled():
                return
            if task.exception() is not None:
                task.print_stack()
        task.add_done_callback(_done_callback)
        setattr(self, taskAttributeName, task)
        return task
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


_NotFoundToken = object()


class readOnlyCachedProperty:

    """
        >>> class Foo:
        ...     @readOnlyCachedProperty
        ...     def calcOnce(self):
        ...         print("calculating")
        ...         return 123
        ...
        >>> f = Foo()
        >>> f.calcOnce
        calculating
        123
        >>> f.calcOnce
        123
        >>> del f.calcOnce
        Traceback (most recent call last):
            ...
        AttributeError: calcOnce is read-only
        >>> f.calcOnce = 134
        Traceback (most recent call last):
            ...
        AttributeError: calcOnce is read-only
    """

    def __init__(self, func):
        self.func = func
        self.name = func.__name__

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.name, _NotFoundToken)
        if value is _NotFoundToken:
            value = self.func(obj)
            obj.__dict__[self.name] = value
        return value

    def __set__(self, obj, value):
        raise AttributeError(f"{self.name} is read-only")

    def __delete__(self, obj):
        raise AttributeError(f"{self.name} is read-only")


class cachedProperty(readOnlyCachedProperty):

    """
        >>> class Foo:
        ...     @cachedProperty
        ...     def calcOnce(self):
        ...         print("calculating")
        ...         return 123
        ...
        >>> f = Foo()
        >>> f.calcOnce
        calculating
        123
        >>> f.calcOnce
        123
        >>> del f.calcOnce
        >>> f.calcOnce
        calculating
        123
        >>> del f.calcOnce
        >>> del f.calcOnce
        >>> f.calcOnce = 134
        >>> f.calcOnce
        134
    """

    def __set__(self, obj, value):
        obj.__dict__[self.name] = value

    def __delete__(self, obj):
        if self.name in obj.__dict__:
            del obj.__dict__[self.name]
