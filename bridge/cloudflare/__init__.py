from typing import Any

from microapi.bridge.cloudflare.http import RequestConverter as BridgeRequestConverter, RequestConverter, ResponseConverter
from microapi.bridge.cloudflare.http import ResponseConverter as BridgeResponseConverter, ClientExecutor as BridgeClientExecutor
from microapi.bridge.cloudflare.kv import Store
from microapi.bridge.cloudflare.queue import Queue, MessageBatchConverter
from microapi.bridge.cloudflare.sql import Database
from microapi.bridge.cloudflare.util import to_py
from microapi.di import Container, ServiceProvider
from microapi.bridge import CloudContext as FrameworkCloudContext
from microapi.kernel import HttpKernel as FrameworkHttpKernel
from microapi.http import ClientExecutor
from microapi.kv import DatabaseStore
from microapi.queue import KVQueue, Queue as FrameworkQueue


class CloudContext(FrameworkCloudContext):
    def __init__(self, context=None, controller=None, env=None):
        super().__init__()
        self._raw = {
            "controller": controller,
            "env": env,
            "context": context
        }
        self.provider_name = "cloudflare"

    async def raw(self) -> dict:
        return self._raw

    async def kv(self, arguments) -> Store:
        if "name" not in arguments:
            raise ValueError("Name must be specified")
        return Store(await self.binding(arguments["name"]))

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

        if name not in env:
            raise RuntimeError(f"Binding {name} not available")

        return env[name]


class App(ServiceProvider):
    def __init__(self, kernel: FrameworkHttpKernel = None, container: Container = None, service_providers = None):
        if kernel is not None and (container is not None or service_providers is not None):
            raise RuntimeError("cannot pass both kernel and container or service_providers")

        if kernel is None:
            kernel = FrameworkHttpKernel(container=container, service_providers=service_providers)

        self.kernel = kernel
        self.container = kernel.container
        self.container.provide(self)

    def services(self):
        yield RequestConverter, lambda _: BridgeRequestConverter()
        yield ResponseConverter, lambda _: BridgeResponseConverter()
        yield ClientExecutor, lambda _: BridgeClientExecutor()

    def on_fetch(self):
        async def handler(request, env):
            request_converter = await self.container.get(RequestConverter)
            response_converter = await self.container.get(ResponseConverter)

            async def container_builder(_: Container):
                _.set(FrameworkCloudContext, lambda _: CloudContext(env=env))

            converted = await request_converter.to_microapi(request)
            response = await self.kernel.handle(converted, container_builder)
            return await response_converter.from_microapi(response)

        return handler

    def on_scheduled(self):
        async def handler(controller, env, ctx):

            async def container_builder(_: Container):
                _.set(FrameworkCloudContext, lambda _: CloudContext(controller=controller, env=env, context=ctx))

            await self.kernel.cron(container_builder)

        return handler

    def on_queue(self):
        async def handler(batch, env, ctx):
            async def container_builder(_: Container):
                _.set(FrameworkCloudContext, lambda _: CloudContext(env=env, context=ctx))

            message_batch = await MessageBatchConverter.to_microapi(batch)
            await self.kernel.queue_batch(message_batch, container_builder)

        return handler
