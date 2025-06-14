from websockets.asyncio.client import connect
import asyncio

from shared.message import RegisterWorker, parse_message
from worker.src.constants import MASTER_IP, MASTER_PORT
from worker.src.logger import set_worker_id


async def main():
    async with connect(f"ws://{MASTER_IP}:{MASTER_PORT}") as websocket:
        await websocket.send(RegisterWorker(sender="worker").serialize())
        while True:
            async for message in websocket:
                msg = parse_message(message)
                if isinstance(msg, RegisterWorker):
                    set_worker_id(msg.worker_id)


if __name__ == "__main__":
    asyncio.run(main())
