import contextlib
import logging

from porcupine import utils

log = logging.getLogger(__name__)


class CallbackHook:
    """Simple object that runs callbacks.

    >>> hook = CallbackHook()
    >>> @hook.connect
    ... def user_callback(value):
    ...     print("user_callback called with", value)
    ...
    >>> hook.run(123)       # usually porcupine does this
    user_callback called with 123

    You can hook multiple callbacks too:

    >>> @hook.connect
    ... def another_callback(value):
    ...     print("another_callback called with", value)
    ...
    >>> hook.run(456)
    user_callback called with 456
    another_callback called with 456

    Hooks have a ``callbacks`` attribute that contains a list of hooked
    functions. It's useful for removing callbacks or checking if a
    callback has been added.

    >>> hook.callbacks == [user_callback, another_callback]
    True

    Errors in the connected functions will be logged to
    ``logging.getLogger(logname)``. The *unhandled_errors* argument
    should be an iterable of exceptions that won't be handled.
    """

    def __init__(self, logname, *, unhandled_errors=()):
        self._log = logging.getLogger(logname)
        self._unhandled = tuple(unhandled_errors)  # isinstance() likes tuples
        self._blocklevel = 0
        self.callbacks = []

    def connect(self, function):
        """Schedule a function to be called when the hook is ran.

        The function is returned too, so this can be used as a
        decorator.
        """
        self.callbacks.append(function)
        return function

    def disconnect(self, function):
        """Undo a :meth:`connect` call."""
        self.callbacks.remove(function)

    def disconnect_all(self):
        """Disconnect all connected callbacks.

        This should be ran when the hook won't be needed anymore.
        """
        self.callbacks.clear()

    def run(self, *args):
        """Run ``callback(*args)`` for each connected callback.

        This does nothing if :meth:`~blocked` is currently running.
        """
        assert self._blocklevel >= 0
        if self._blocklevel > 0:
            return

        for callback in self.callbacks:
            try:
                callback(*args)
            except Exception as e:
                if isinstance(e, self._unhandled):
                    raise e
                self._log.exception("%s doesn't work",
                                    utils.nice_repr(callback))

    @contextlib.contextmanager
    def blocked(self):
        """Prevent the callbacks from running temporarily.

        Use this as a context manager, like this::

            with some_hook.blocked():
                # do something that would normally run the callbacks
        """
        self._blocklevel += 1
        try:
            yield
        finally:
            self._blocklevel -= 1


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
