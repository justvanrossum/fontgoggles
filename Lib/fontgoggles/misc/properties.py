import weakref


_NotFoundToken = object()


class cachedProperty:

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
        >>> f.calcOnce = 134
        Traceback (most recent call last):
            ...
        AttributeError: calcOnce is read-only
        >>> del f.calcOnce
        >>> f.calcOnce
        calculating
        123
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
        # Mark cache as stale
        if self.name in obj.__dict__:
            del obj.__dict__[self.name]


class hookedProperty:

    """Property that calls a hook whenever its value changed, or
    when it got deleted.

    The `hook` should be a callable, that will be called with the
    owner of property as the first argument, and is therefore
    effectively a method of the owner.

    The hook will only be called when the value is actually
    different, so when clients set it to the same value several
    times in a row, the hook is only called once.

    Likewise, the hook itself can rely on the fact that the value
    has actually changed when it is called.
    """

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
        if self.name not in obj.__dict__ or obj.__dict__[self.name] != value:
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


if __name__ == "__main__":
    import doctest
    doctest.testmod()
