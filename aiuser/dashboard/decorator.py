import typing


def dashboard_page(*args, **kwargs):
    """ Decorator to mark functions as dashboard pages """
    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func
    return decorator 