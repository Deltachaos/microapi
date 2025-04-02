from miniapi.bridge.cloudflare.http import RequestConverter as BridgeRequestConverter, RequestConverter, ResponseConverter
from miniapi.bridge.cloudflare.http import ResponseConverter as BridgeResponseConverter
from miniapi.di import Container, ServiceProvider
from miniapi.kernel import HttpKernel as FrameworkHttpKernel


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
            request_converter = await self.container.get(RequestConverter)
            response_converter = await self.container.get(ResponseConverter)

            converted = await request_converter.to_miniapi(request)
            response = await self.kernel.handle(converted)
            return await response_converter.from_miniapi(response)

        return handler

    def on_scheduled(self):
        async def handler(controller, env, ctx):
            raise NotImplementedError()

        return handler
