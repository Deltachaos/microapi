from .http import ClientExecutor as BridgeClientExecutor
from .http.server import CronScheduler, HttpServer
from .sql import Database
from ...di import Container, ServiceProvider
from ...bridge import CloudContext as FrameworkCloudContext
from ...kernel import HttpKernel as FrameworkHttpKernel
from ...http import ClientExecutor
from asyncio import new_event_loop, gather
import os


class CloudContext(FrameworkCloudContext):
    async def sql(self, arguments) -> Database:
        if "name" not in arguments:
            raise ValueError("Name must be specified")

        return Database(arguments["name"])

    async def env(self, name, default=None) -> str|None:
        if name not in os.environ:
            return default
        return os.environ[name]


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
        yield ClientExecutor, lambda _: BridgeClientExecutor()
        yield FrameworkCloudContext, lambda _: CloudContext()

    def run(self, host='0.0.0.0', port=8000, cron_interval=30):
        """Run the application with HTTP server and cron scheduler"""
        async def main():
            async def container_builder(_: Container):
                _.set(CloudContext, lambda _: CloudContext())

            # Create instances
            cron_scheduler = CronScheduler(self, container_builder, interval=cron_interval)
            http_server = HttpServer(self, container_builder, host=host, port=port)

            # Run both in parallel
            await gather(
                cron_scheduler.run(),
                http_server.run()
            )

        new_event_loop().run_until_complete(main())