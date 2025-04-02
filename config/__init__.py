from microapi.di import ServiceProvider
from microapi.event import EventDispatcher
from microapi.event_subscriber import RoutingEventSubscriber, SecurityEventSubscriber
from microapi.router import Router
from microapi.http import Client, ClientFactory
from microapi.di import Container
from microapi.security import Security, TokenStore, Firewall, DefaultVoter


class FrameworkServiceProvider(ServiceProvider):
    def services(self):
        # HTTP
        yield Router, lambda _: Router(_.tagged_generator('controller'))
        yield EventDispatcher, lambda _: EventDispatcher(_.tagged_generator('event_subscriber'))
        yield RoutingEventSubscriber

        # Util
        yield Client, FrameworkServiceProvider.client_factory

    @staticmethod
    async def client_factory(_: Container) -> Client:
        client_factory = await _.get(ClientFactory)
        return client_factory.create()


class SecurityServiceProvider(ServiceProvider):
    def __init__(self, firewall_paths = None):
        self.firewall_paths = firewall_paths

    def services(self):
        # Security
        yield TokenStore
        yield Firewall, SecurityServiceProvider.firewall_factory(self.firewall_paths)
        yield Security, SecurityServiceProvider.security_factory
        yield SecurityEventSubscriber
        yield DefaultVoter

    @staticmethod
    async def security_factory(_: Container) -> Security:
        token_store = await _.get(TokenStore)
        return Security(token_store, _.tagged_generator('security_voter'))

    @staticmethod
    def firewall_factory(paths = None):
        if paths is None:
            paths = {}

        async def firewall_factory(_: Container) -> Firewall:
            security = await _.get(Security)
            token_store = await _.get(TokenStore)
            firewall = Firewall(security, token_store, _.tagged_generator('token_resolver'))

            for path, role in paths.items():
                await firewall.add(path, role)

            return firewall

        return firewall_factory
