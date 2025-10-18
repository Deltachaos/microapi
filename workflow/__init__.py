import inspect
import json

from .. import Container
from ..di import tag
from ..event import Event, listen
from ..util import logger, to_list


class Workflow:
    pass


class WorkflowManager:
    def __init__(self, _workflows):
        self._workflows = _workflows

    async def _get_workflow_class(self, cls: str):
        workflows = []
        for workflow_cls, get_workflow in self._workflows():
            workflow_cls_str = workflow_cls.__module__ + "." + workflow_cls.__name__
            workflows.append(workflow_cls_str)
            if cls == workflow_cls_str:
                return await get_workflow()

        raise ValueError(f"Unknown workflow: {cls}. Available workflows: {','.join(workflows)}")

    async def _get_workflow_method(self, workflow_class: str, method: str, args):
        workflow = await self._get_workflow_class(workflow_class)
        _method = getattr(workflow, method)

        async def run():
            result = _method(**args)
            if inspect.isasyncgen(result):
                async for item in result:
                    if item is not None:
                        next_func, next_args = item
                        yield await self._get_dispatch(next_func, next_args)
            else:
                item = await result
                if item is not None:
                    next_func, next_args = item
                    yield await self._get_dispatch(next_func, next_args)

        return run

    async def _get_dispatch(self, func: callable, args: dict = None, idempotency_key: bool | str = True):
        if args is None:
            args = {}
        workflow_cls = func.__module__ + "." + func.__qualname__.split(".")[0]
        method = func.__name__
        return workflow_cls, method, args

    async def dispatch(self, func: callable, args: dict = None):
        dispatch = await self._get_dispatch(func, args)
        if next is None:
            return

        dispatch_workflow_cls, dispatch_method, dispatch_args = dispatch

        logger(__name__).info(f'Workflow dispatch: {dispatch_workflow_cls}.{dispatch_method} - {json.dumps(dispatch_args)}')
        await self.queue(dispatch_workflow_cls, dispatch_method, dispatch_args)

    async def queue(self, workflow_cls: str, method: str, args):
        await self.step(workflow_cls, method, args)

    async def step(self, workflow_cls: str, method: str, args):
        logger(__name__).info(f'Workflow step: {workflow_cls}.{method} - {json.dumps(args)}')
        _method = await self._get_workflow_method(workflow_cls, method, args)
        result = _method()

        if inspect.isasyncgen(result):
            async for item in result:
                if item is not None:
                    dispatch_workflow_cls, dispatch_method, dispatch_args = item
                    await self.step(dispatch_workflow_cls, dispatch_method, dispatch_args)
        else:
            items = await result
            for item in await to_list(items):
                if item is not None:
                    dispatch_workflow_cls, dispatch_method, dispatch_args = item
                    await self.step(dispatch_workflow_cls, dispatch_method, dispatch_args)



class WorkflowManagerFactory:
    def __init__(self, _: Container):
        self._ = _

    async def create(self):
        return WorkflowManager(self._.tagged_generator('workflow'))


class WorkflowEvent(Event):
    def __init__(self, workflow_cls, method, args):
        super().__init__()
        self.workflow_cls = workflow_cls
        self.method = method
        self.args = args
        self.result = None


@tag('event_subscriber')
class WorkflowEventSubscriber:
    def __init__(self, manager: WorkflowManager):
        self._manager = manager

    @listen(WorkflowEvent)
    async def workflow(self, event: WorkflowEvent):
        event.result = await self._manager.step(event.workflow_cls, event.method, event.args)
