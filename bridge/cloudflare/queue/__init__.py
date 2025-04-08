import json

from microapi.bridge.cloudflare.util import to_js, to_py
from microapi.queue import Queue as FrameworkQueue, MessageBatch as FrameworkMessageBatch, Message as FrameworkMessage



class Message(FrameworkMessage):
    def __init__(self, message):
        #    print(message.id)
        #    print(message.timestamp)
        #    print(message.body)
        #    print(message.attempts)
        #    print(message.ack)
        #    print(message.retry)
        self._message = message

    async def get(self) -> dict:
        data = to_py(self._message.body)
        if "message" not in data:
            raise RuntimeError("Message body is missing 'message'")
        return data["message"]

    async def ack(self):
        self._message.ack()

    async def retry(self):
        self._message.retry()


class MessageBatch(FrameworkMessageBatch):
    def __init__(self, batch):
        self._batch = batch

    @property
    def queue_name(self):
        return to_py(self._batch.queue)

    async def messages(self):
        for message in self._batch.messages:
            yield Message(message)

    async def consumed_count(self):
        raise len(self._batch.messages)

    async def ack_all(self):
        self._batch.ackAll()

    async def retry_all(self):
        self._batch.retryAll()


class Queue(FrameworkQueue):
    def __init__(self, queue, queue_name):
        self.queue = queue
        self.queue_name = queue_name

    async def originates(self, message_batch: MessageBatch) -> bool:
        if not isinstance(message_batch, MessageBatch):
            return False

        return message_batch.queue_name == self.queue_name

    async def send(self, data: dict, idempotency_key: str | bool = None):
        if idempotency_key is None:
            idempotency_key = await self.idempotency_key(data)

        await self.queue.send(to_js({
             "key": idempotency_key,
             "message": data
        }))


class MessageBatchConverter:
    @staticmethod
    async def to_microapi(batch) -> MessageBatch:
        return MessageBatch(batch)