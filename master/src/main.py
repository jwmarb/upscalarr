import asyncio
import threading
from websockets.asyncio.server import serve
from websockets import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol
from master.src.client import Client
from master.src.logger import logger
from master.src.changehandler import ChangeHandler
from watchdog.observers import Observer
from master.src.config import config
from master.src.constants import PORT
from shared.message import RegisterWorker, parse_message


async def handler(websocket: WebSocketServerProtocol):
    worker = Client(websocket)
    logger.info(f"Client ({worker.remote_address()}) connected to websocket")
    try:
        async for message in websocket:
            msg = parse_message(message)
            if isinstance(msg, RegisterWorker):
                try:
                    await worker.register()
                except Exception as e:
                    logger.error(
                        f"Failed to register worker. (Remote IP: {worker.remote_address()})")
                    print(e)
                    break
            else:
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
