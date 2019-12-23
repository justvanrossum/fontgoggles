import asyncio
import functools
import logging
import weakref


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
        except Exception:
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


class hookedProperty:

    def __init__(self, hook, default=_NotFoundToken):
        self.hook = hook
        self.default = default

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, cls=None):
        try:
            return obj.__dict__[self.name]
        except KeyError:
            if self.default is _NotFoundToken:
                raise AttributeError(self.name)
            else:
                return self.default

    def __set__(self, obj, value):
        obj.__dict__[self.name] = value
        self.hook(obj)

    def __delete__(self, obj):
        try:
            del obj.__dict__[self.name]
        except KeyError:
            raise AttributeError(self.name)
        self.hook(obj)


class delegateProperty:

    def __init__(self, delegateAttributeName):
        self.delegateAttributeName = delegateAttributeName

    def __set_name__(self, owner, name):
        # This is Python >= 3.6
        self.propertyName = name

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        delegate = getattr(obj, self.delegateAttributeName)
        return getattr(delegate, self.propertyName)

    def __set__(self, obj, value):
        delegate = getattr(obj, self.delegateAttributeName)
        setattr(delegate, self.propertyName, value)

    def __delete__(self, obj):
        delegate = getattr(obj, self.delegateAttributeName)
        delattr(delegate, self.propertyName)


class weakrefCallbackProperty:

    def __init__(self, doc=None):
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self.weakrefCallbackName = "_weakrefCallback_" + name

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        weakrefCallback = getattr(obj, self.weakrefCallbackName, None)
        if weakrefCallback is None:
            return None
        return weakrefCallback()

    def __set__(self, obj, value):
        if value is None:
            self.__delete__(obj)
        else:
            try:
                weakMethod = weakref.WeakMethod(value)
            except TypeError:
                setattr(obj, self.weakrefCallbackName, lambda: value)
            else:
                setattr(obj, self.weakrefCallbackName, weakMethod)

    def __delete__(self, obj):
        try:
            delattr(obj, self.weakrefCallbackName)
        except AttributeError:
            pass
