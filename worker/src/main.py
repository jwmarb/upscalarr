from pathlib import Path
import pathlib
import signal
from typing import Callable
from websockets import ClientConnection
from websockets.asyncio.client import connect
import asyncio

from shared.message import AddUpscaleJob, AddUpscaleJobInProgress, RegisterWorker, UpscaleJobComplete, parse_message, IsWorkerAvailable, SourceModifiedOrDeleted
from worker.src.constants import MASTER_IP, MASTER_PORT
from worker.src.logger import set_worker_id, logger
from worker.src.config import config
import asyncio
import os
import shutil

UPSCALE_SUCCESS = 0


async def handle_upscale_job(msg: AddUpscaleJob, websocket: ClientConnection, worker_id: int | None, src_pids: dict[str, int]):
    logger.info(f"Upscaling {msg.file}")
    src_path = Path(msg.file)
    season = src_path.parent
    series_name = season.parent
    upscaling_prog_folder = Path(
        config.upscaling) / series_name.name / season.name
    Path.mkdir(upscaling_prog_folder,
               parents=True, exist_ok=True)
    dest_path = upscaling_prog_folder / \
        src_path.name.replace("1080p", "2160p")
    proc = await asyncio.create_subprocess_shell(f"{config.cmd} -i \"{msg.file}\" -o \"{dest_path}\"", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    # print(f"pid: {proc.pid}")
    src_pids[msg.file] = proc.pid
    await websocket.send(AddUpscaleJobInProgress(pid=proc.pid, worker_id=worker_id, src_path=str(src_path), dest_path=str(dest_path)).serialize())
    # stdout_lines, stderr_lines = [], []

    # async def stream_output(stream, logger_func: Callable[[str], None], accumulator: list[str]):
    #     async for line in stream:
    #         decoded = line.decode().rstrip()
    #         print(decoded, end="\r", flush=True)
    #         accumulator.append(decoded)

    # await asyncio.gather(
    #     stream_output(proc.stdout, logger.info, stdout_lines),
    #     stream_output(proc.stderr, logger.error, stderr_lines)
    # )
    await proc.wait()
    # output = "\n".join(stdout_lines)
    # summary_idx = output.find(
    # "====== Video2X Processing summary ======")
    # if summary_idx != -1:
    # output = output[summary_idx:]
    # logger.info(f"\n{output}")
    logger.info(f"Finished \"{src_path}\"\n\tReturn Code:{proc.returncode}")
    is_success = proc.returncode == UPSCALE_SUCCESS

    del src_pids[msg.file]

    if not is_success:
        dest_path.unlink(missing_ok=True)
    else:
        upscaled_path = Path(
            config.upscaled) / series_name.name / season.name / dest_path.name
        upscaled_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(dest_path, upscaled_path)
        src_path.unlink(missing_ok=True)

    await websocket.send(UpscaleJobComplete(is_success=is_success, worker_id=worker_id, dest_path=str(dest_path), src_path=str(src_path)).serialize())


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
                    asyncio.create_task(handle_upscale_job(
                        msg, websocket, worker_id, src_pids))


if __name__ == "__main__":
    asyncio.run(main())
