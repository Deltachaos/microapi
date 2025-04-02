from typing import Any

from miniapi.bridge.cloudflare.http import RequestConverter as BridgeRequestConverter, RequestConverter, ResponseConverter
from miniapi.bridge.cloudflare.http import ResponseConverter as BridgeResponseConverter
from miniapi.di import Container, ServiceProvider
from miniapi.bridge import CloudContext as FrameworkCloudContext
from miniapi.kernel import HttpKernel as FrameworkHttpKernel


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

    async def binding(self, name: str) -> Any:
        if self._raw["env"] is None:
            raise RuntimeError("Environment not set")

        if name not in self._raw["env"]:
            raise RuntimeError(f"Binding {name} not available")

        return self._raw["env"][name]


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

    def on_fetch(self):
        async def handler(request, env):
            self.container.set(CloudContext, lambda _: CloudContext(env=env))
            request_converter = await self.container.get(RequestConverter)
            response_converter = await self.container.get(ResponseConverter)

            converted = await request_converter.to_miniapi(request)
            response = await self.kernel.handle(converted)
            return await response_converter.from_miniapi(response)

        return handler

    def on_scheduled(self):
        async def handler(controller, env, ctx):
            self.container.set(CloudContext, lambda _: CloudContext(controller=controller, env=env, context=ctx))
            await self.kernel.cron()

        return handler
