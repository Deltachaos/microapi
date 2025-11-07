from .bridge import CloudContext
from .di import Container
from .queue import QueueBinding
from .util import call_async


class CloudContextQueueBindingFactory:
    @staticmethod
    def create(binding: type[QueueBinding], reference = None):
        async def factory(_: Container):
            context = await _.get(CloudContext)
            resolved_reference = reference
            if resolved_reference is None:
                resolved_reference = binding
            elif callable(reference):
                resolved_reference = await call_async(reference, _, context)
            _queue = await context.queue(resolved_reference)
            created = binding()
            created.set_queue(_queue)
            return created

        return factory