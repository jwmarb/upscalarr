import asyncio
import threading
import yaml
from websockets.asyncio.server import serve
from websockets import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol
from .client import Client
from .logger import logger
from .changehandler import ChangeHandler
from watchdog.observers import Observer
import os

from master.src.config import Config


PORT = os.environ.get("PORT", 8765)
CONFIG = os.environ.get("CONFIG_PATH", "config.yaml")

with open(CONFIG, "r") as f:
    raw = yaml.safe_load(f)
    config = Config(**raw)


async def handler(websocket: WebSocketServerProtocol):
    worker = Client(websocket)
    logger.info(
        f"Registering new worker node with an ID of {worker.id()} (Remote IP: {worker.remote_address()})")
    try:
        async for message in websocket:
            await websocket.send(message)
    except ConnectionClosed:
        logger.info(
            f"Worker {worker.id()} disconnected. (Remote IP: {worker.remote_address()})")
    finally:
        worker.unregister()


async def main():
    logger.info(f"Listening for changes in {config.source}")
    loop = asyncio.get_event_loop()

    event_handler = ChangeHandler(loop=loop)
    observer = Observer()
    observer.schedule(event_handler, config.source, recursive=True)
    observer_thread = threading.Thread(target=observer.start)
    observer_thread.daemon = True
    observer_thread.start()

    async with serve(handler, "0.0.0.0", PORT) as server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
