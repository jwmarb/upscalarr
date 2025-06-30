import asyncio
import os
import threading
import time
import sys
import re
from worker.src.util import Worker
import socket


class Info:

    # series->season->episode->info
    _upscales_terminal_session: dict[str, dict[str, dict[str, str]]] = {}
    _lock = False
    _stop_event = threading.Event()

    @staticmethod
    def prepare_stream(series_name: str, season: str, episode: str):
        Info._lock = True
        if series_name not in Info._upscales_terminal_session:
            Info._upscales_terminal_session[series_name] = {}
        if season not in Info._upscales_terminal_session[series_name]:
            Info._upscales_terminal_session[series_name][season] = {}
        Info._upscales_terminal_session[series_name][season][episode] = "waiting..."
        Info._lock = False

    @staticmethod
    async def handle_stream(stream: asyncio.StreamReader, series_name: str, season: str, episode: str):
        buffer = b""
        while True:
            chunk = await stream.read(512)
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > 512:
                buffer = buffer[-512:]
            Info._upscales_terminal_session[series_name][season][episode] = buffer.decode(
                errors="replace")

    @staticmethod
    def finish_stream(series_name: str, season: str, episode: str):
        Info._lock = True
        del Info._upscales_terminal_session[series_name][season][episode]
        if not Info._upscales_terminal_session[series_name][season]:
            del Info._upscales_terminal_session[series_name][season]
        if not Info._upscales_terminal_session[series_name]:
            del Info._upscales_terminal_session[series_name]
        os.system('clear')
        Info._lock = False

    @staticmethod
    def listen():
        Info._stop_event.clear()
        t = threading.Thread(target=Info._listener, daemon=True)
        t.start()

    @staticmethod
    def stop():
        Info._stop_event.set()

    @staticmethod
    def _listener():
        n = 0
        while not Info._stop_event.is_set():
            if Info._upscales_terminal_session and not Info._lock:
                # Move up to overwrite previous block, if not first time
                if n > 0:
                    sys.stdout.write(f"\x1b[{n}A")

                sys.stdout.write(
                    f'Worker {Worker.id()} ({socket.gethostbyname(socket.gethostname())})\n')
                lines_to_print = 1  # Reset line counter for this iteration

                for series in Info._upscales_terminal_session:
                    if Info._lock:
                        break
                    if not Info._upscales_terminal_session[series]:
                        break
                    for season in Info._upscales_terminal_session[series]:
                        if not Info._upscales_terminal_session[series][season]:
                            break
                    sys.stdout.write('\x1b[2K' + series + '\n')
                    lines_to_print += 1
                    for season in Info._upscales_terminal_session[series]:
                        if Info._lock:
                            break
                        sys.stdout.write('\x1b[2K' + '\t' + season + '\n')
                        lines_to_print += 1
                        for episode in Info._upscales_terminal_session[series][season]:
                            if Info._lock:
                                break
                            episode_stdout = Info._upscales_terminal_session[series][season][episode]
                            if episode_stdout:
                                trimmed_episode_title = re.search(
                                    r'S\d{2}E\d{2}', episode).group()
                                if episode_stdout == "waiting...":
                                    sys.stdout.write(
                                        '\x1b[2K' + '\t\t' + trimmed_episode_title + '> ' + episode_stdout + '\n')
                                    lines_to_print += 1
                                else:
                                    frames_idx = episode_stdout.rfind("frame=")
                                    if frames_idx != -1:
                                        sys.stdout.write(
                                            '\x1b[2K' + '\t\t' + trimmed_episode_title + '> ' + episode_stdout[frames_idx:].replace("\r", "") + '\n')
                                        lines_to_print += 1
                sys.stdout.write('\n')
                sys.stdout.flush()
                n = lines_to_print + 1  # Save for next loop

            time.sleep(0.1)
