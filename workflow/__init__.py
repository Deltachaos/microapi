import hashlib
import inspect
import json

from microapi.di import tag
from microapi.queue import Queue, MessageBatch, BatchMessageHandler
from microapi.util import logger


class Workflow:
    pass


@tag('workflow_manager')
class WorkflowManager:
    async def get_step(self, message: dict):
        raise NotImplementedError()

    async def dispatch(self, func: callable, args: dict):
        raise NotImplementedError()

    async def step(self, message: dict):
        method, args = await self.get_step(message)
        result = method(**args)

        if inspect.isasyncgen(result):
            async for next_func, next_args in result:
                await self.dispatch(next_func, next_args)
        else:
            await result


class QueueWorkflowManager(WorkflowManager):
    def __init__(self, queue: Queue, workflows):
        self._queue = queue
        self._workflows = workflows

    async def _get_workflow(self, cls: str):
        for workflow_cls, get_workflow in self._workflows():
            workflow_cls_str = workflow_cls.__module__ + "." + workflow_cls.__name__
            if cls == workflow_cls_str:
                return await get_workflow()

        raise ValueError(f"Unknown workflow: {cls}")

    async def get_queue(self) -> Queue:
        return self._queue

    async def supports(self, queue: Queue):
        return await self.get_queue() == queue

    async def get_step(self, message: dict):
        workflow_cls_name = message["workflow"]
        step_name = message["step"]
        args = message["args"]

        workflow = await self._get_workflow(workflow_cls_name)

        method = getattr(workflow, step_name)
        return method, args

    async def dispatch(self, func: callable, args: dict, idempotency_key: bool | str = True):
        logger(__name__).debug(f'Workflow dispatch: {func} - {idempotency_key} - {json.dumps(args)}')
        workflow_cls = func.__module__ + "." + func.__qualname__.split(".")[0]
        method_name = func.__name__
        payload = {
            "workflow": workflow_cls,
            "step": method_name,
            "args": args,
        }
        await self._queue.send(payload, idempotency_key)


@tag("queue_message_handler")
class WorkflowBatchHandler(BatchMessageHandler):
    def __init__(self, workflow_managers):
        self._workflow_managers = workflow_managers

    async def get_workflow_manager(self, queue: Queue) -> WorkflowManager | None:
        for workflow_cls, get_workflow_manager in self._workflow_managers():
            workflow_manager = await get_workflow_manager()
            if isinstance(workflow_manager, QueueWorkflowManager) and await workflow_manager.supports(queue):
                return workflow_manager
        return None

    async def supports(self, queue: Queue) -> bool:
        return await self.get_workflow_manager(queue) is not None

    async def handle(self, batch: MessageBatch, queue: Queue):
        workflow_manager = await self.get_workflow_manager(queue)
        if workflow_manager is not None:
            async for message in batch.messages():
                data = await message.get()
                try:
                    await workflow_manager.step(data)
                    await message.ack()
                except Exception as e:
                    logger(__name__).exception("Workflow for message failed", exc_info=e)
                    await message.retry()
