import asyncio
import time
from master.src.hashed_queue import HashedQueue
import os

from pydantic import BaseModel

from master.src.config import config
from master.src.logger import logger
from shared.message import AddUpscaleJob, IsWorkerAvailable, SourceModifiedOrDeleted
from .client import Client
from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileMovedEvent
from pathlib import Path

CREATED = "created"
MODIFIED = "modified"
OPENED = "opened"
CLOSED = "closed"
CLOSED_NO_WRITE = "closed_no_write"
DELETED = "deleted"
MOVED = "moved"

file_extensions = set([".mkv", ".avi", ".mp4"])


class UpscaleJob(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    src_file: str
    dest_file: str
    pid: int
    worker: Client


class ChangeHandler(FileSystemEventHandler):
    _upscale_jobs: list[UpscaleJob] = []
    _upscale_queue: HashedQueue[str] = HashedQueue()

    def has_upscale_jobs(worker: Client):
        for job in ChangeHandler._upscale_jobs:
            if job.worker.id() == worker.id():
                return True
        return False

    def remove_upscale_job(src_file: str):
        ChangeHandler._upscale_jobs = [
            s for s in ChangeHandler._upscale_jobs if s.src_file != src_file]

    def remove_upscale_jobs_of(worker: Client):
        removed_upscale_jobs = [
            s for s in ChangeHandler._upscale_jobs if s.worker.id() == worker.id()]
        ChangeHandler._upscale_jobs = [
            s for s in ChangeHandler._upscale_jobs if s.worker.id() != worker.id()]
        for s in removed_upscale_jobs:
            ChangeHandler.queue_upscale(s.src_file)

    def add_upscale_job(upscale_job: UpscaleJob):
        logger.info(
            f"Upscale ({upscale_job.src_file}) on Worker {upscale_job.worker.id()} with PID {upscale_job.pid}")
        ChangeHandler._upscale_jobs.append(upscale_job)

    def __init__(self, loop):
        self._loop = loop

    def queue_upscale(file_path: str):
        """
        Will add an upscale, assigning it to whatever worker node is available.
        """
        ChangeHandler._upscale_queue.enqueue(file_path)

    def queue_listener(self) -> None:
        # upon initialization, check for existing source files and add them to the queue
        existing_files = Path(config.source).rglob("*")
        for f in existing_files:
            if f.is_file():
                logger.info(f"Tracking {f}")
                ChangeHandler.queue_upscale(str(f))
        while True:
            # iterate through each upscale, and for each iteration, iterate through all available clients
            # a client is considered unavailable when at least one upscale job has failed
            # a client becomes available the moment it finishes an upscale job
            while len(ChangeHandler._upscale_queue) > 0:
                for client in Client.clients():
                    if client.is_available():
                        file_path = ChangeHandler._upscale_queue.dequeue()
                        logger.info(
                            f"Creating upscale job ({file_path}) on Worker {client.id()}")
                        asyncio.run_coroutine_threadsafe(client.send_message(
                            AddUpscaleJob(file=file_path)), self._loop)
                        break
                time.sleep(0.1)
            time.sleep(0.1)

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return

        # message = f"{event.event_type} - {event.src_path}"

        # if file_path.suffix in file_extensions:
        # logger.info(message)
        file = Path(event.dest_path)
        # if event.event_type == DELETED:
        # print(message)
        if event.event_type == CREATED or event.event_type == MODIFIED or event.event_type == MOVED or event.event_type == CLOSED:
            if event.event_type == CREATED:
                file = Path(event.src_path)
            if file.suffix in file_extensions:
                logger.info(f"Tracking {file}")
                if event.event_type == CLOSED or event.event_type == CREATED:
                    ChangeHandler.queue_upscale(event.src_path)
                else:
                    ChangeHandler.queue_upscale(event.dest_path)

        elif event.event_type == DELETED:
            logger.info(f"File deleted ({event.src_path})")
            asyncio.run_coroutine_threadsafe(Client.broadcast(
                SourceModifiedOrDeleted(file=event.src_path)), self._loop)

    # def on_moved(self, event: FileMovedEvent):
    #     if event.is_directory:
    #         return
    #     file = Path(event.dest_path)
    #     if file.suffix in file_extensions:
    #         logger.info(f"Tracking {os.path.basename(file)}")
    #         asyncio.run_coroutine_threadsafe(
    #             Client.queue_upscale(event.dest_path), self._loop)
