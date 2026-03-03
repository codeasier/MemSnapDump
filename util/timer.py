import time
import logging
from typing import Callable, Optional
from functools import wraps


def timer(name: Optional[str] = None, logger: Optional[logging.Logger] = None):
    def decorator(func: Callable):
        _name = func.__name__ if not name else name
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            info = f"{_name} took {end - start:.4f} seconds"
            if logger:
                logger.info(info)
            else:
                print(info)
            return result

        return wrapper

    return decorator
