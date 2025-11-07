import inspect
import json
from enum import Enum

from .. import Container
from ..di import tag
from ..event import Event, listen
from ..queue import Queue, QueueBinding, BatchMessageHandler, MessageBatch
from ..util import logger, to_list

class WorkflowExecution(str, Enum):
    AUTO = "auto"
    STEP = "step"
    QUEUE = "queue"
    DISPATCH = "dispatch"

    @staticmethod
    def from_str(label):
        if label == "auto":
            return WorkflowExecution.AUTO
        elif label == "step":
            return WorkflowExecution.STEP
        elif label == "queue":
            return WorkflowExecution.QUEUE
        elif label == "dispatch":
            return WorkflowExecution.DISPATCH
        else:
            raise NotImplementedError

class Workflow:
    pass


class WorkflowManager:
    def __init__(self, _workflows, queue: Queue = None):
        self._workflows = _workflows
        self._queue_binding = queue

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
                        yield await self._get_dispatch(item)
            else:
                item = await result
                if item is not None:
                    yield await self._get_dispatch(item)

        return run

    async def _get_dispatch(self, item, options_default = None):
        if options_default is None:
            options_default = WorkflowExecution.AUTO

        func = None
        args = None
        options = None
        if len(item) >= 1:
            func = item[0]

        if len(item) >= 2:
            args = item[1]

        if len(item) >= 3:
            options = item[2]

        if func is None:
            raise ValueError("logic error")

        if args is None:
            args = {}

        if options is None:
            options = options_default

        workflow_cls = func.__module__ + "." + func.__qualname__.split(".")[0]
        method = func.__name__
        return workflow_cls, method, args, options

    async def dispatch_batch(self, items: list):
        queue_batch = []
        for item in items:
            dispatch = await self._get_dispatch(item, WorkflowExecution.DISPATCH)
            if item is None:
                continue

            queue_batch.append(dispatch)

        await self._spread(queue_batch)

    async def dispatch(self, func: callable, args: dict = None, options: str = None):
        if options is None:
            options = WorkflowExecution.DISPATCH

        await self.dispatch_batch([(func, args, options)])

    async def step(self, workflow_cls: str, method: str, args):
        await self._step(workflow_cls, method, args)

    async def _step(self, workflow_cls: str, method: str, args):
        logger(__name__).info(f'Workflow step: {workflow_cls}.{method} - {json.dumps(args)}')
        _method = await self._get_workflow_method(workflow_cls, method, args)
        result = _method()
        batch = []

        if inspect.isasyncgen(result):
            async for item in result:
                if item is not None:
                    batch.append(item)
        else:
            items = await result
            for item in await to_list(items):
                if item is not None:
                    batch.append(item)

        await self._spread(batch)

    async def _dispatch(self, items: list):
        await self._queue(items)

    async def _queue(self, items: list):
        for item in items:
            dispatch_workflow_cls, dispatch_method, dispatch_args = item
            if self._queue_binding is None:
                await self._step(dispatch_workflow_cls, dispatch_method, dispatch_args)
            else:
                await self._queue_binding.send({
                    "workflow_cls": dispatch_workflow_cls,
                    "method": dispatch_method,
                    "args": dispatch_args
                })

    async def _get_option(self, workflow_cls: str, method: str, args):
        return WorkflowExecution.STEP

    async def _spread(self, items: list):
        dispatch_batch = []
        queue_batch = []

        for item in items:
            if item is None:
                continue

            dispatch_workflow_cls, dispatch_method, dispatch_args, dispatch_options = item
            if dispatch_options is None:
                dispatch_options = WorkflowExecution.AUTO

            new_item = (dispatch_workflow_cls, dispatch_method, dispatch_args)

            if dispatch_options == WorkflowExecution.AUTO:
                dispatch_options = await self._get_option(dispatch_workflow_cls, dispatch_method, dispatch_args)

            if not issubclass(type(dispatch_options), WorkflowExecution):
                dispatch_options = WorkflowExecution.from_str(dispatch_options)

            logger(__name__).info(f'Workflow spread {dispatch_options}: {dispatch_workflow_cls}.{dispatch_method} - {json.dumps(dispatch_args)}')

            # TODO implement idempotency

            if dispatch_options == WorkflowExecution.DISPATCH:
                dispatch_batch.append(new_item)
            elif dispatch_options == WorkflowExecution.QUEUE:
                queue_batch.append(new_item)
            elif dispatch_options == WorkflowExecution.STEP:
                await self._step(dispatch_workflow_cls, dispatch_method, dispatch_args)
            else:
                raise ValueError(f"cannot find a dispatch option for {dispatch_options} of type {type(dispatch_options)}")

        if len(dispatch_batch) > 0:
            await self._dispatch(dispatch_batch)

        if len(queue_batch) > 0:
            await self._queue(queue_batch)


@tag('queue')
class WorkflowQueue(QueueBinding):
    pass


class WorkflowManagerFactory:
    def __init__(self, _: Container):
        self._ = _

    async def create(self):
        return WorkflowManager(
            self._.tagged_generator('workflow'),
            await self._.get(WorkflowQueue)
        )


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


@tag("queue_message_handler")
class WorkflowQueueBatchHandler(BatchMessageHandler):
    def __init__(self, manager: WorkflowManager):
        self._manager = manager

    async def supports(self, queue: Queue) -> bool:
        return isinstance(queue, WorkflowQueue)

    async def handle(self, batch: MessageBatch, queue: Queue):
        async for message in batch.messages():
            data = await message.get()
            try:
                await self._manager.step(data["workflow_cls"], data["method"], data["args"])
                await message.ack()
            except Exception as e:
                await message.retry()
