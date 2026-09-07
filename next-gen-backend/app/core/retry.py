# app/core/retry.py

import logging
import time
from functools import wraps
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)


def retry_on_exception(
    func: Callable | None = None,
    *,
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Simple retry decorator with exponential backoff.

    Usage:

        @retry_on_exception(retries=3, delay=1.0)
        def do_something():
            ...
    """

    def decorator(f: Callable):
        @wraps(f)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(retries + 1):
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= retries:
                        logger.error(
                            f"{f.__name__} failed after {attempt + 1} attempts: {e}"
                        )
                        break

                    logger.warning(
                        f"{f.__name__} failed, attempt {attempt + 1}/{retries + 1}: {e}. "
                        f"Retrying in {current_delay:.2f}s."
                    )

                    time.sleep(current_delay)
                    current_delay *= backoff

            raise last_exception

        return wrapper

    if func is not None:
        return decorator(func)

    return decorator