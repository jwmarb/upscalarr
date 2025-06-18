from pathlib import Path
import signal
from typing import Callable
from websockets.asyncio.client import connect
import asyncio

from shared.message import AddUpscaleJob, AddUpscaleJobInProgress, RegisterWorker, UpscaleJobComplete, parse_message, IsWorkerAvailable, SourceModifiedOrDeleted
from worker.src.constants import MASTER_IP, MASTER_PORT
from worker.src.logger import set_worker_id, logger
from worker.src.config import config
import asyncio
import os

UPSCALE_SUCCESS = 0


async def main():
    async with connect(f"ws://{MASTER_IP}:{MASTER_PORT}") as websocket:
        worker_id = None
        src_pids: dict[str, int] = {}
        await websocket.send(RegisterWorker(sender="worker").serialize())
        while True:
            async for message in websocket:
                msg = parse_message(message)
                if isinstance(msg, RegisterWorker):
                    set_worker_id(msg.worker_id)
                    worker_id = msg.worker_id
                elif isinstance(msg, IsWorkerAvailable):
                    logger.info(
                        "Sending master node the worker's availability: AVAILABLE")
                    await websocket.send(IsWorkerAvailable(
                        sender="worker", worker_id=worker_id, is_available=True).serialize())
                elif isinstance(msg, SourceModifiedOrDeleted):
                    if msg.file in src_pids.keys():
                        logger.error(
                            "An upscale job has been interrupted due to the modification or deletion of a file.")
                        os.kill(src_pids[msg.file], signal.SIGKILL)
                elif isinstance(msg, AddUpscaleJob):
                    logger.info(f"Upscaling {msg.file}")
                    src_path = Path(msg.file)
                    dest_path = src_path.with_name("test.mkv")
                    proc = await asyncio.create_subprocess_shell(f"{config.cmd} -i \"{msg.file}\" -o \"{dest_path}\"", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    # print(f"pid: {proc.pid}")
                    src_pids[msg.file] = proc.pid
                    await websocket.send(AddUpscaleJobInProgress(pid=proc.pid, worker_id=worker_id, src_path=str(src_path), dest_path=str(dest_path)).serialize())
                    stdout_lines, stderr_lines = [], []

                    async def stream_output(stream, logger_func: Callable[[str], None], accumulator: list[str]):
                        async for line in stream:
                            decoded = line.decode().rstrip()
                            print(decoded, end="\r", flush=True)
                            accumulator.append(decoded)

                    await asyncio.gather(
                        stream_output(proc.stdout, logger.info, stdout_lines),
                        stream_output(proc.stderr, logger.error, stderr_lines)
                    )
                    await proc.wait()
                    output = "\n".join(stdout_lines)
                    output = output[output.index(
                        "====== Video2X Processing summary ======"):]
                    logger.info(f"\n{output}")
                    logger.info(f"return code: {proc.returncode}")
                    await websocket.send(UpscaleJobComplete(is_success=proc.returncode == UPSCALE_SUCCESS, worker_id=worker_id, dest_path=str(dest_path), src_path=str(src_path)).serialize())

if __name__ == "__main__":
    asyncio.run(main())
