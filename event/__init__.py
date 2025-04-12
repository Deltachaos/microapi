from threading import Event
from typing import Type, Callable

from microapi.util import call_async, logger


def listen(_event: Type[Event], priority: int = 0):
    def decorator(func: Callable):
        if not hasattr(func, "_"):
            func._subscribed_events = []
        func._subscribed_events.append((priority, _event))
        return func
    return decorator


class Event:
    def __init__(self):
        self._propagation_stopped = False

    def stop_propagation(self):
        self._propagation_stopped = True

    def is_propagation_stopped(self) -> bool:
        return self._propagation_stopped


class EventDispatcher:
    def __init__(self, subscribers: Callable):
        self._subscribers = subscribers

    async def dispatch(self, event: Event) -> Event:
        """Dispatches an event to all registered async listeners."""
        event_type = type(event)
        logger(__name__).info(f"Dispatching {event_type}")
        async for listener in self.listeners(event_type):
            await call_async(listener, event)
            if event.is_propagation_stopped():
                break
        return event

    async def listeners_priority(self, event_type: Type[Event]):
        """Returns the list of listeners for a given event type."""
        for service_type, service_get in self._subscribers():
            for attr_name in dir(service_type):
                attr = getattr(service_type, attr_name)
                if callable(attr) and hasattr(attr, "_subscribed_events"):
                    _subscribed_events = getattr(attr, "_subscribed_events")
                    for priority, _event in _subscribed_events:
                        if _event == event_type:
                            logger(__name__).debug(f"Found listener {service_type}.{attr_name}")
                            service = await service_get()
                            yield priority, getattr(service, attr_name)

    async def listeners(self, event_type: Type[Event]):
        items = []
        async for priority, listener in self.listeners_priority(event_type):
            items.append((priority, listener))

        items.sort(key=lambda x: x[0])

        for item in items:
            yield item[1]
