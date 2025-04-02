import copy
import inspect

from microapi.di import tag, Container
from microapi.event import listen
from microapi.kernel import RequestEvent, ControllerEvent, ExceptionEvent, HttpException
from microapi.router import Router


@tag('event_subscriber')
class RoutingEventSubscriber:
    def __init__(self, container: Container, router: Router):
        self._container = container
        self._router = router

    @listen(RequestEvent)
    def router(self, event: RequestEvent):
        if "_controller" not in event.request.attributes:
            result = self._router.match(event.request)
            if result is not None:
                cls, method_name, params = result
                for key, value in params.items():
                    event.request.attributes[key] = copy.deepcopy(value)

                event.request.attributes["_controller"] = cls
                event.request.attributes["_controller_method"] = method_name

    @listen(ControllerEvent)
    async def controller(self, event: ControllerEvent):
        if "_controller" in event.request.attributes:
            controller_service = event.request.attributes["_controller"]
            if inspect.isclass(controller_service) and "_controller_method" in event.request.attributes:
                controller_method = event.request.attributes["_controller_method"]
                controller_service = await self._container.get(event.request.attributes["_controller"])
                event.controller = getattr(controller_service, controller_method)
            elif callable(controller_service):
                event.controller = controller_service

    @listen(ExceptionEvent)
    async def exception(self, event: ExceptionEvent):
        if isinstance(event.exception, HttpException):
            event.response = event.exception.to_response()
