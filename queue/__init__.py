import uuid
import asyncio
from typing import List

from microapi.kv import JSONStore


class Message:
    async def get(self) -> dict:
        raise NotImplementedError()

    async def ack(self):
        raise NotImplementedError()

    async def retry(self):
        raise NotImplementedError()


class MessageBatch:
    async def messages(self):
        raise NotImplementedError()

    async def ack_all(self):
        raise NotImplementedError()

    async def retry_all(self):
        raise NotImplementedError()


class BatchMessageHandler:
    async def handle(self, batch: MessageBatch):
        raise NotImplementedError()


class Queue:
    async def send(self, data: dict):
        raise NotImplementedError()


class ConsumableQueue(Queue):
    def set_message_handler(self, handler: BatchMessageHandler):
        raise NotImplementedError()


class PullQueue(ConsumableQueue):
    async def process(self):
        raise NotImplementedError()


class KVMessage(Message):
    def __init__(self, store: JSONStore, key: str, data: dict):
        self.store = store
        self.key = key
        self.data = data
        self._acked = False
        self._retried = False

    async def get(self) -> dict:
        return self.data.get("message")

    async def ack(self):
        self._acked = True
        await self.store.delete(self.key)

    async def retry(self):
        self._retried = True
        self.data["retries"] = self.data.get("retries", 0) + 1
        if self.data["retries"] >= self.data.get("max_retries", 3):
            await self.store.delete(self.key)
        else:
            await self.store.put(self.key, self.data)


class KVMessageBatch(MessageBatch):
    def __init__(self, messages: List[KVMessage]):
        self.messages = messages

    async def messages(self):
        return self.messages

    async def ack_all(self):
        await asyncio.gather(*(msg.ack() for msg in self.messages if not msg._acked and not msg._retried))

    async def retry_all(self):
        await asyncio.gather(*(msg.retry() for msg in self.messages if not msg._acked and not msg._retried))


class KVQueue(PullQueue):
    def __init__(self, store: JSONStore, max_retries=3, batch_size: int = 50):
        self.store = store
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.handler = None

    def set_message_handler(self, handler: BatchMessageHandler):
        self.handler = handler

    async def send(self, data: dict):
        key = str(uuid.uuid4())
        await self.store.put(key, {
            "retries": 0,
            "max_retries": self.max_retries,
            "message": data
        })

    async def process(self):
        if self.handler is None:
            return

        i = 0
        messages = []
        for key in await self.store.list():
            i = i + 1
            if i > self.batch_size:
                break
            data = await self.store.get(key)
            if data:
                messages.append(KVMessage(self.store, key, data))

        if i == 0:
            return

        batch = KVMessageBatch(messages)
        try:
            await self.handler.handle(batch)
        except Exception:
            await batch.retry_all()
            raise
        else:
            await batch.ack_all()
