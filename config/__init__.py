from miniapi.di import ServiceProvider
from miniapi.event import EventDispatcher
from miniapi.event_subscriber import RoutingEventSubscriber
from miniapi.router import Router


class FrameworkServiceProvider(ServiceProvider):
    def services(self):
        yield Router, lambda _: Router(_.tagged_generator('controller'))
        yield EventDispatcher, lambda _: EventDispatcher(_.tagged_generator('event_subscriber'))
        yield RoutingEventSubscriber
