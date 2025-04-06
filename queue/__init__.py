import json
import time
import uuid
import asyncio
from typing import List

from microapi.kv import JSONStore, Store
from microapi.util import logger


class Queue:
    async def send(self, data: dict):
        raise NotImplementedError()


class Message:
    async def get(self) -> dict:
        raise NotImplementedError()

    async def ack(self):
        raise NotImplementedError()

    async def retry(self):
        raise NotImplementedError()


class MessageBatch:
    async def messages(self):
        yield

    async def consumed_count(self):
        raise NotImplementedError()

    async def ack_all(self):
        raise NotImplementedError()

    async def retry_all(self):
        raise NotImplementedError()


class BatchMessageHandler:
    async def supports(self, queue: Queue):
        return True

    async def handle(self, batch: MessageBatch, queue: Queue):
        raise NotImplementedError()


class ConsumableQueue(Queue):
    def set_handler(self, batch: BatchMessageHandler):
        raise NotImplementedError()


class PullQueue(ConsumableQueue):
    async def pull(self) -> MessageBatch | None:
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
        self._messages = messages

    async def messages(self):
        for message in self._messages:
            yield message

    async def consumed_count(self):
        return len(self._messages)

    async def ack_all(self):
        await asyncio.gather(*(msg.ack() for msg in self._messages if not msg._acked and not msg._retried))

    async def retry_all(self):
        await asyncio.gather(*(msg.retry() for msg in self._messages if not msg._acked and not msg._retried))

    def __str__(self):
        return f"KVMessageBatch messages={len(self._messages)}"


class KVQueue(PullQueue):
    def __init__(self, store: Store, max_retries=3, batch_size: int = 50):
        self.store = JSONStore(store)
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.handler = None

    async def send(self, data: dict):
        key = str(int(time.time())) + ":" + str(uuid.uuid4())
        await self.store.put(key, {
            "retries": 0,
            "max_retries": self.max_retries,
            "message": data
        })

    async def pull(self) -> MessageBatch | None:
        i = 0
        messages = []
        async for key in self.store.list():
            i = i + 1
            if i > self.batch_size:
                break
            data = await self.store.get(key)
            logger(__name__).debug(f"Pulled message {key} {json.dumps(data)}")
            if data:
                messages.append(KVMessage(self.store, key, data))

        if i == 0:
            return None

        return KVMessageBatch(messages)


class QueueAware:
    async def set_queue(self, queue: Queue|None):
        raise NotImplementedError()

    async def get_queue(self) -> Queue|None:
        raise NotImplementedError()


class QueueBinding(Queue, QueueAware):
    def __init__(self):
        self._queue = None

    def set_queue(self, queue):
        self._queue = queue

    async def get_queue(self):
        return self._queue

    async def send(self, data: dict):
        if self._queue is None:
            raise RuntimeError("Queue is not set")
        await self._queue.send(data)


class BatchMessageHandlerManager:
    def __init__(self, handlers):
        self._handlers = handlers

    async def is_supported(self, queue: Queue):
        for _, get_handler in self._handlers():
            handler = await get_handler()
            if await handler.supports(queue):
                return True
        return False

    async def handle(self, batch: MessageBatch, queue: Queue):
        for _, get_handler in self._handlers():
            handler = await get_handler()
            if await handler.supports(queue):
                try:
                    logger(__name__).info(f"Processed batch {batch}")
                    await handler.handle(batch, queue)
                except Exception:
                    logger(__name__).info(f"Processed batch {batch} unsuccessful")
                    await batch.retry_all()
                    raise
                else:
                    logger(__name__).info(f"Processed batch {batch} successfully")
                    await batch.ack_all()


class QueueProcessor:
    def __init__(self, queues, manager: BatchMessageHandlerManager):
        self._queues = queues
        self._handler_manager = manager

    async def pull(self):
        for _, get_queue in self._queues():
            queue = await get_queue()
            if not await self._handler_manager.is_supported(queue):
                continue

            real_queue = queue
            if isinstance(queue, QueueAware):
                real_queue = await queue.get_queue()

            if isinstance(real_queue, PullQueue):
                logger(__name__).debug(f"Process queue: {type(queue)}")
                messages = await real_queue.pull()
                if messages:
                    yield queue, messages

    async def process(self, batch_size: int = 0):
        handled = 0
        handled_last_batch = 1
        while handled_last_batch > 0 and (batch_size == 0 or batch_size < handled):
            handled_last_batch = 0
            async for queue, messages in self.pull():
                await self._handler_manager.handle(messages, queue)
                handled_last_batch = await messages.consumed_count()
            handled += handled_last_batch
