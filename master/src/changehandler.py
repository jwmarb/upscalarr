import asyncio
from .client import Client
from watchdog.events import FileSystemEventHandler, FileSystemEvent

CREATED = "created"
MODIFIED = "modified"
OPENED = "opened"
CLOSED = "closed"
CLOSED_NO_WRITE = "closed_no_write"


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, loop):
        self._loop = loop

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return

        message = f"{event.event_type} - {event.src_path}"
        asyncio.run_coroutine_threadsafe(Client.broadcast(message), self._loop)
