from microapi.di import ServiceProvider
from microapi.event import EventDispatcher
from microapi.event_subscriber import RoutingEventSubscriber
from microapi.router import Router
from microapi.http import Client, ClientFactory
from microapi.di import Container


class FrameworkServiceProvider(ServiceProvider):
    def services(self):
        yield Router, lambda _: Router(_.tagged_generator('controller'))
        yield EventDispatcher, lambda _: EventDispatcher(_.tagged_generator('event_subscriber'))
        yield RoutingEventSubscriber
        yield Client, FrameworkServiceProvider.client_factory

    @staticmethod
    async def client_factory(_: Container) -> Client:
        client_factory = await _.get(ClientFactory)
        return client_factory.create()
