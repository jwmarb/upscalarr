from websockets.legacy.server import WebSocketServerProtocol
from typing import Set, Self
from .logger import logger


class Client:
    _connected_clients: Set[Self] = set()

    @staticmethod
    async def broadcast(data):
        for c in Client.clients():
            await c._websocket.send(data)

    @staticmethod
    def clients():
        return Client._connected_clients

    def __init__(self, websocket: WebSocketServerProtocol):
        self._id = len(Client.clients())
        self._connected_clients.add(self)
        self._websocket = websocket

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
