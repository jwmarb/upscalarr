from pathlib import Path
import pathlib
import signal
import time
from typing import Callable
from websockets import ClientConnection
from websockets.asyncio.client import connect
import asyncio

from shared.message import AddUpscaleJob, AddUpscaleJobInProgress, RegisterWorker, UpscaleJobComplete, parse_message,  SourceModifiedOrDeleted
from worker.src.info import Info
from worker.src.logger import logger
from worker.src.util import Worker
from shared.config import config
import asyncio
import os
import shutil
import json

UPSCALE_SUCCESS = 0
CODECS = ("x264", "h264", "x265", "hevc", "MPEG2", "MPEG", "XviD",
          "DivX", "VC1", "AV1", "VP6", "VP7", "VP8", "VP9", "WMV")
RESOLUTIONS = ("2160p", "1440p", "1080p", "720p",
               "480p", "360p", "DVD", "SDTV")


async def ffprobe(file: Path, entries: tuple[str]):
    process = await asyncio.create_subprocess_shell(f"ffprobe -v error -select_streams v:0 -show_entries stream={','.join(entries)} -of json \"{file}\"", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.DEVNULL)
    stdout, _ = await process.communicate()
    info = json.loads(stdout.decode())
    return info


async def rename(out_path: Path):
    if not config.worker.rename_output:
        return out_path

    info = await ffprobe(out_path, ('codec_name', 'height'))
    height: int = info['streams'][0]['height']
    codec_name: str = info['streams'][0]['codec_name'].upper()
    new_name: Path = out_path
    for codec in CODECS:
        new_name = new_name.with_name(new_name.name.replace(codec, codec_name))
    for resolution in RESOLUTIONS:
        new_name = new_name.with_name(
            new_name.name.replace(resolution, f'{height}p'))
    return new_name


async def get_video_resolution(video_path: Path | str):
    info = await ffprobe(video_path, ('height',))
    height: int = info['streams'][0]['height']
    return str(height) + "p"


async def handle_upscale_job(msg: AddUpscaleJob, websocket: ClientConnection, src_pids: dict[str, int]):
    # logger.info(f"Upscaling {msg.file}")
    try:
        src_path = Path(msg.file)
        season = src_path.parent
        series_name = season.parent
        folder = config.get_folder(series_name.parent)
        upscaling_prog_folder = Path(
            folder.work) / series_name.name / season.name
        Path.mkdir(upscaling_prog_folder,
                   parents=True, exist_ok=True)
        dest_path = upscaling_prog_folder / src_path.name
        height = await get_video_resolution(src_path)

        if type(config.worker.video2x) == str:
            cmd = f"{config.worker.video2x} -i \"{msg.file}\" -o \"{dest_path}\""
        elif height in config.worker.video2x:
            cmd = f"{config.worker.video2x[height]} -i \"{msg.file}\" -o \"{dest_path}\""
        elif "default" in config.worker.video2x:
            cmd = f"{config.worker.video2x["default"]} -i \"{msg.file}\" -o \"{dest_path}\""
        else:
            raise Exception(
                "No \"default\" key provided. This must be provided as a necessary fallback.")

        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.DEVNULL)
        # print(f"pid: {proc.pid}")
        src_pids[msg.file] = proc.pid
        Info.prepare_stream(series_name.name, season.name, src_path.name)
        await websocket.send(AddUpscaleJobInProgress(pid=proc.pid, worker_id=Worker.id(), src_path=str(src_path), dest_path=str(dest_path)).serialize())
        await asyncio.gather(
            Info.handle_stream(proc.stdout, series_name.name,
                               season.name, src_path.name),
        )
        await proc.wait()
        Info.finish_stream(series_name.name, season.name, src_path.name)
        is_success = proc.returncode == UPSCALE_SUCCESS

        del src_pids[msg.file]

        if not is_success:
            dest_path.unlink(missing_ok=True)
        else:
            upscaled_path = await rename(dest_path)
            upscaled_path = Path(folder.out) / series_name.name / \
                season.name / upscaled_path.name
            upscaled_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(dest_path, upscaled_path)
            if config.worker.delete_on_completion:
                src_path.unlink(missing_ok=True)

        await websocket.send(UpscaleJobComplete(is_success=is_success, worker_id=Worker.id(), dest_path=str(dest_path), src_path=str(src_path)).serialize())
    except Exception as e:
        logger.error(e)
        await websocket.send(UpscaleJobComplete(is_success=False, worker_id=Worker.id(), dest_path=str(dest_path), src_path=str(src_path)).serialize())


async def main():
    async with connect(f"ws://{config.worker.master_host.ip}:{config.worker.master_host.port}") as websocket:
        src_pids: dict[str, int] = {}
        await websocket.send(RegisterWorker(sender="worker").serialize())
        Info.listen()
        while True:
            async for message in websocket:
                msg = parse_message(message)
                if isinstance(msg, RegisterWorker):
                    Worker.set_worker_id(msg.worker_id)
                elif isinstance(msg, SourceModifiedOrDeleted):
                    if msg.file in src_pids.keys():
                        logger.error(
                            "An upscale job has been interrupted due to the modification or deletion of a file.")
                        os.kill(src_pids[msg.file], signal.SIGKILL)
                elif isinstance(msg, AddUpscaleJob):
                    asyncio.create_task(handle_upscale_job(
                        msg, websocket, src_pids))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Info.stop()
