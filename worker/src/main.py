#!/usr/bin/env python

"""Client using the asyncio API."""

from websockets.asyncio.client import connect
import logging
import asyncio
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def hello():
    async with connect("ws://localhost:8765") as websocket:
        await websocket.send("0")
        while True:
            async for message in websocket:
                print(message)


if __name__ == "__main__":
    asyncio.run(hello())
