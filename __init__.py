from microapi.bridge import CloudContext
from microapi.di import Container
from microapi.queue import QueueBinding


class CloudContextQueueBindingFactory:
    @staticmethod
    def create(binding: type[QueueBinding], reference):
        async def factory(_: Container):
            context = await _.get(CloudContext)
            _queue = await context.queue(reference)
            created = binding()
            created.set_queue(_queue)
            return created

        return factory