import asyncio
import logging
from typing import Callable, Any


def logger(name = "app"):
    _ = logging.getLogger(name)
    logging.basicConfig(level=logging.DEBUG)
    return _


async def call_async(listener: Callable, *args, **kwargs) -> Any:
    if asyncio.iscoroutinefunction(listener):
        return await listener(*args, **kwargs)
    else:
        #return await asyncio.to_thread(listener, *args, **kwargs)
        return listener(*args, **kwargs)