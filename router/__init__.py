import re
from typing import Dict, Type, Tuple, Callable, Optional

from ..http import Request
from ..util import logger


def route(_route: str, method: str = "GET"):
    def decorator(func: Callable):
        if not hasattr(func, "_routes"):
            func._routes = []
        func._routes.append((_route, method))
        return func
    return decorator


def get(_route: str):
    return route(_route, "GET")


def post(_route: str):
    return route(_route, "POST")


def option(_route: str):
    return route(_route, "OPTION")


def delete(_route: str):
    return route(_route, "DELETE")


def put(_route: str):
    return route(_route, "PUT")


def patch(_route: str):
    return route(_route, "PATCH")


class Router:
    def __init__(self, controllers: Callable):
        self._controllers = controllers

    def routes(self):
        for cls, _ in self._controllers():
            for method_name in dir(cls):
                attr = getattr(cls, method_name)
                if callable(attr) and hasattr(attr, "_routes"):
                    for route, http_method in attr._routes:
                        regex, param_names = self._convert_route_to_regex(route)
                        yield http_method, regex, cls, method_name, param_names

    def _convert_route_to_regex(self, route: str) -> Tuple[re.Pattern, list[str]]:
        """
        Convert a route like '/user/{id}' to a regex pattern.
        """
        param_names = re.findall(r"\{(\w+)\}", route)  # Extract placeholder names
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", route)  # Convert to regex
        return re.compile(f"^{pattern}$"), param_names

    def match(self, request: Request) -> Optional[Tuple[Type, str, Dict[str, str]]]:
        """
        Match the request path against stored routes.
        Returns the handler function and a dictionary of extracted parameters.
        """
        path = request.path
        for http_method, regex, cls, method_name, param_names in self.routes():
            logger(__name__).debug(f"Match path {http_method} {path} against {regex}")
            if request.method != http_method:
                continue
            match = regex.match(path)
            if match:
                logger(__name__).debug(f"Matched route {cls}.{method_name}")
                params = {name: match.group(name) for name in param_names}
                return cls, method_name, params
        return None
