__version__ = "0.4.2"

__all__ = ["create_app", "__version__"]


def create_app(*args, **kwargs):
    from .gateway import create_app as _create_app

    return _create_app(*args, **kwargs)
