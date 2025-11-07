import uuid

from microapi import Container, CloudContext
from microapi.bridge.cloudflare.util import to_js
from microapi.util import to_list
from microapi.workflow import WorkflowManager as FrameworkWorkflowManager, WorkflowExecution, WorkflowQueue


class WorkflowManager(FrameworkWorkflowManager):
    def __init__(self, binding, step_engine, _workflows, _queue_binding):
        self._binding = binding
        self._step_engine = step_engine
        super().__init__(_workflows, _queue_binding)

    async def _get_workflow_method(self, workflow_class: str, method: str, args):
        _method = await super()._get_workflow_method(workflow_class, method, args)

        if self._step_engine is None:
            return _method

        @self._step_engine.do(workflow_class + "." + method)
        async def run():
            return await to_list(_method())

        return run

    async def _get_option(self, workflow_cls: str, method: str, args):
        if self._step_engine is None:
            return WorkflowExecution.QUEUE

        return WorkflowExecution.STEP

    async def _dispatch(self, items: list):
        _id_prefix = str(uuid.uuid4())
        index = 0
        max_batch_size = 100
        splitted = [items[i:i + max_batch_size] for i in range(0, len(items), max_batch_size)]
        for items in splitted:
            batch = []
            for item in items:
                index = index + 1
                _id = _id_prefix + "-" + str(index)
                workflow_cls, method, args = item
                options = to_js({
                    "id": _id,
                    "params": {
                        "workflow_cls": workflow_cls,
                        "method": method,
                        "args": args
                    }
                })
                batch.append(options)
                await self._binding.create(options)
            #await self._binding.createBatch(batch)

    async def _queue(self, items: list):
        if self._queue_binding is None:
            await self._dispatch(items)
        else:
            await super()._queue(items)


class WorkflowManagerFactory:
    def __init__(self, _: Container):
        self._ = _

    async def create(self):
        context = await self._.get(CloudContext)
        raw = await context.raw()
        step_engine = None
        if "step" in raw:
            step_engine = raw["step"]

        binding = None
        binding_name = await context.config("default.workflow")
        if binding_name is not None:
            binding = await context.binding(binding_name)

        return WorkflowManager(
            binding,
            step_engine,
            self._.tagged_generator('workflow'),
            await self._.get(WorkflowQueue)
        )