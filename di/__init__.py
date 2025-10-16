import inspect
import copy
from typing import Callable, Tuple, List, Any

from ..util import call_async, logger


def tag(_tag: str):
    def decorator(func: Callable):
        if not hasattr(func, "_tags"):
            func._tags = []
        logger(__name__).debug(f"Tag '{type(func)}' with {_tag}")
        func._tags.append(_tag)
        return func
    return decorator


class Container:
    def __init__(self, services=None):
        self._services = services or {}
        self._instances = {}
        self.set(Container, self)

    def provide(self, service_provider: 'ServiceProvider'):
        logger(__name__).debug(f"Register provider '{type(service_provider)}'")
        for svs in service_provider.services():
            provider = None
            if isinstance(svs, tuple):
                name, provider = svs
            else:
                name = svs
            self.set(name, provider)

    def set(self, name, provider=None):
        """Register a service provider by name."""
        logger(__name__).debug(f"Register '{name}' factory")
        self._services[name] = provider

    def build(self):
        """Create a new container instance with fresh instances."""
        return Container(copy.deepcopy(self._services))

    async def has(self, name):
        return name in self._services

    async def get(self, name):
        """Resolve a service by name, returning the same instance every time."""
        if name in self._instances:
            return self._instances[name]

        if not await self.has(name):
            raise ValueError(f"Service '{name}' not found")

        provider = self._services.get(name)
        if provider is None:
            logger(__name__).debug(f"Construct '{name}' using autowire")
            provider = self.autowire(name)
        else:
            logger(__name__).debug(f"Construct '{name}' using factory")

        if callable(provider):
            instance = await call_async(provider, self)
        else:
            instance = provider

        self._instances[name] = instance
        return instance

    def service_ids(self):
        return self._services.keys()

    def tagged_ids(self, _tag: str):
        for cls in self.service_ids():
            if inspect.isclass(cls) or inspect.isfunction(cls):
                if hasattr(cls, "_tags") and _tag in cls._tags:
                    yield cls

    async def tagged(self, _tag: str):
        for name in self.tagged_ids(_tag):
            yield await self.get(name)

    def tagged_generator(self, _tag: str):
        def generate():
            for cls in self.tagged_ids(_tag):
                async def do_get():
                    return await self.get(cls)
                yield cls, do_get

        return generate

    def autowire(self, name):
        async def do_call(_):
            return await _.call(name)
        return do_call

    def remove(self, name):
        """Unregister a service by name."""
        self._services.pop(name, None)
        self._instances.pop(name, None)

    async def call(self, func, args_dict=None):
        """Resolve services required by a function based on argument types."""
        # Get the function's signature and inspect argument types
        if args_dict is None:
            args_dict = {}
        signature = inspect.signature(func)
        resolved_args = {}

        for param_name, param in signature.parameters.items():
            param_type = param.annotation
            if param_name in args_dict:
                resolved_args[param_name] = args_dict[param_name]
            elif param_type is not inspect.Parameter.empty:
                if not await self.has(param_type):
                    raise RuntimeError(f"Argument '{param_name}' has no registered service '{param_type}'")
                service = await self.get(param_type)
                resolved_args[param_name] = service

        return await call_async(func, **resolved_args)


class ServiceProvider:
    def services(self):
        yield from []
