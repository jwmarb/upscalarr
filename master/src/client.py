import asyncio
from websockets.legacy.server import WebSocketServerProtocol
from typing import Self
from shared.message import Message, RegisterWorker, IsWorkerAvailable
from .logger import logger
from collections import deque


class Client:
    _connected_clients: set[Self] = set()

    @staticmethod
    async def broadcast(data: Message):
        for c in Client.clients():
            await c.send_message(data)

    @staticmethod
    def clients():
        return Client._connected_clients

    def from_websocket(websocket: WebSocketServerProtocol):
        for c in Client.clients():
            if c._websocket.id == c._websocket.id:
                return c

        return None

    def __init__(self, websocket: WebSocketServerProtocol):
        self._id: int = -1
        self._websocket = websocket
        self._is_available = True

    def is_available(self):
        return self._is_available

    def handle_event(self, event):
        pass

    async def register(self):
        self._id = len(Client._connected_clients)
        logger.info(
            f"Registered new worker node with an ID of {self.id()} (Remote IP: {self.remote_address()})")
        Client._connected_clients.add(self)
        await self._websocket.send(RegisterWorker(sender="master", worker_id=self.id()).serialize())

    def unregister(self):
        logger.info(
            f"Worker {self._id} disconnected. (Remote IP: {self.remote_address()})")
        Client._connected_clients.remove(self)

    def id(self):
        return self._id

    def remote_address(self):
        if type(self._websocket.remote_address) == tuple:
            host, port = self._websocket.remote_address
            return f"{host}:{port}"
        return None

    async def send_message(self, msg: Message):
        await self._websocket.send(msg.serialize())
