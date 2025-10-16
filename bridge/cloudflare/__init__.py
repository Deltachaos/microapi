from typing import Any
from workers import WorkflowEntrypoint, WorkerEntrypoint, Response

from .http import RequestConverter as BridgeRequestConverter, RequestConverter, ResponseConverter
from .http import ResponseConverter as BridgeResponseConverter, ClientExecutor as BridgeClientExecutor
from .kv import Store, ExpiringStore
from .queue import Queue, MessageBatchConverter
from .sql import Database
from .util import to_py
from ...config import FrameworkServiceProvider
from ...di import Container, ServiceProvider
from ...bridge import CloudContext as FrameworkCloudContext
from ...kernel import HttpKernel as FrameworkHttpKernel
from ...http import ClientExecutor
from ...kv import DatabaseStore
from ...queue import KVQueue, Queue as FrameworkQueue
from ...util import logger


class CloudContext(FrameworkCloudContext):
    def __init__(self, context=None, controller=None, env=None, features=None):
        super().__init__()
        self._raw = {
            "controller": controller,
            "env": env,
            "context": context,
            "features": features or []
        }
        self.provider_name = "cloudflare"

    async def raw(self) -> dict:
        return self._raw

    async def kv(self, arguments) -> Store:
        if "name" not in arguments:
            raise ValueError("Name must be specified")
        return Store(await self.binding(arguments["name"]))

    async def expiring_kv(self, arguments, ttl: int = None) -> ExpiringStore:
        if "name" not in arguments:
            raise ValueError("Name must be specified")
        return ExpiringStore(await self.binding(arguments["name"]), ttl)

    async def sql(self, arguments) -> Database:
        if "name" not in arguments:
            raise ValueError("Name must be specified")
        return Database(await self.binding(arguments["name"]))

    async def queue(self, arguments) -> FrameworkQueue:
        if "table" in arguments:
            table = arguments["table"]
            key_column = arguments["key_column"] if "key_column" in arguments else "_key"
            value_column = arguments["value_column"] if "value_column" in arguments else "_value"
            store = DatabaseStore(await self.sql(arguments), table, key_column, value_column)
            return KVQueue(store)
        elif "kv" in arguments:
            store = await self.kv(arguments)
            return KVQueue(store)
        else:
            if "name" not in arguments or "queue" not in arguments:
                raise ValueError("name and queue must be specified")
            binding = await self.binding(arguments["name"])
            return Queue(binding, arguments["queue"])

    async def env(self, name: str, default=None) -> str|None:
        try:
            return await self.binding(name)
        except RuntimeError:
            return default

    async def binding(self, name: str) -> Any:
        if self._raw["env"] is None:
            raise RuntimeError("Environment not set")

        env = to_py(self._raw["env"])

        if not hasattr(env, name):
            raise RuntimeError(f"Binding {name} not available")

        return getattr(env, name)


class App(ServiceProvider):
    def __init__(self, kernel: FrameworkHttpKernel = None, container: Container = None, service_providers = None, free_tier = False):
        if kernel is not None and (container is not None or service_providers is not None):
            raise RuntimeError("cannot pass both kernel and container or service_providers")

        if kernel is None:
            kernel = FrameworkHttpKernel(container=container, service_providers=service_providers)

        self.free_tier = free_tier
        self.kernel = kernel
        self.container = kernel.container
        self.container.provide(self)

    def features(self):
        if self.free_tier:
            return [
                "fetch",
                "cron",
                "kv",
                "d1"
            ]

        return [
            "fetch",
            "cron",
            "kv",
            "d1",
            "queue"
        ]

    def services(self):
        yield RequestConverter, lambda _: BridgeRequestConverter()
        yield ResponseConverter, lambda _: BridgeResponseConverter()
        yield ClientExecutor, lambda _: BridgeClientExecutor()

    def on_fetch(self):
        async def handler(request, env, ctx=None):
            request_converter = await self.container.get(RequestConverter)
            response_converter = await self.container.get(ResponseConverter)

            async def container_builder(_: Container):
                _.set(FrameworkCloudContext, lambda _: CloudContext(env=env, context=ctx))

            converted = await request_converter.to_microapi(request)
            response = await self.kernel.handle(converted, container_builder)
            return await response_converter.from_microapi(response)

        return handler

    def on_scheduled(self):
        async def handler(controller, env, ctx):

            async def container_builder(_: Container):
                _.set(FrameworkCloudContext, lambda _: CloudContext(controller=controller, env=env, context=ctx))

            actions = []
            if not "queue" in self.features():
                actions = ["queue"]

            await self.kernel.cron(container_builder, actions)

        return handler

    def on_queue(self):
        async def handler(batch, env, ctx):
            async def container_builder(_: Container):
                _.set(FrameworkCloudContext, lambda _: CloudContext(env=env, context=ctx))

            message_batch = await MessageBatchConverter.to_microapi(batch)
            await self.kernel.queue_batch(message_batch, container_builder)

        return handler

    def on_run(self):
        async def handler(event, step, env, ctx):
            async def container_builder(_: Container):
                _.set(FrameworkCloudContext, lambda _: CloudContext(env=env, context=ctx))

            # TODO call kernel

        return handler

class FrameworkAppFactory:
    def service_providers(self):
        yield FrameworkServiceProvider()

    def create(self) -> App:
        return App(service_providers=self.service_providers())


class FrameworkEntrypoint(WorkerEntrypoint):
    def __init__(self, ctx, env):
        self.env = env
        self.ctx = ctx
        self.app = self.app_factory().create()

    def app_factory(self) -> FrameworkAppFactory:
        return FrameworkAppFactory()

    async def fetch(self, request):
        handler = self.app.on_fetch()
        return await handler(request, self.env, self.ctx)

    async def scheduled(self, controller, *args):
        handler = self.app.on_scheduled()
        return await handler(controller, self.env, self.ctx)

    async def queue(self, batch, *args):
        handler = self.app.on_queue()
        return await handler(batch, self.env, self.ctx)


class FrameworkWorkflowEntrypoint(WorkflowEntrypoint):
    def app_factory(self) -> FrameworkAppFactory:
        return FrameworkAppFactory()

    async def on_run(self, event, step):
        app = self.app_factory().create()
        handler = app.on_run()
        return await handler(event, step, self.env, self.ctx)
