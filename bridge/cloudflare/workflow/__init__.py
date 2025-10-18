import inspect

from microapi import Container, CloudContext
from microapi.bridge.cloudflare.util import to_js
from microapi.util import to_list
from microapi.workflow import WorkflowManager as FrameworkWorkflowManager


class WorkflowManager(FrameworkWorkflowManager):
    def __init__(self, binding, step_engine, _workflows):
        self._binding = binding
        self._step_engine = step_engine
        super().__init__(_workflows)

    async def _get_workflow_method(self, workflow_class: str, method: str, args):
        _method = await super()._get_workflow_method(workflow_class, method, args)

        @self._step_engine.do(workflow_class + "." + method)
        async def run():
            return await to_list(_method())

        return run

    async def queue(self, workflow_cls: str, method: str, args):
        options = to_js({
            "params": {
                "workflow_cls": workflow_cls,
                "method": method,
                "args": args
            }
        })
        await self._binding.create(options)


class WorkflowManagerFactory:
    def __init__(self, _: Container):
        self._ = _

    async def create(self):
        context = await self._.get(CloudContext)
        raw = await context.raw()
        step_engine = raw["step"]

        binding = None
        binding_name = await context.config("workflow.default")
        if binding_name is not None:
            binding = await context.binding(binding_name)

        return WorkflowManager(binding, step_engine, self._.tagged_generator('workflow'))