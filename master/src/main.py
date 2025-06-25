import asyncio
import threading
import time
from websockets.asyncio.server import serve
from websockets import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol
from master.src.client import Client
from master.src.logger import logger
from master.src.changehandler import ChangeHandler, UpscaleJob
from watchdog.observers import Observer
from master.src.config import config
from master.src.constants import PORT
from shared.message import AddUpscaleJobInProgress, RegisterWorker, UpscaleJobComplete, parse_message, IsWorkerAvailable
import os

failed_upscales: dict[str, int] = {}


def write_errored_upscale(failed_upscale_path: str):
    logger.warning(
        f"{failed_upscale_path} has reattempted {config.max_reattempts} times but failed all of them. It will be skipped!")
    with open(config.error_upscales, 'a' if os.path.exists(config.error_upscales) else 'w') as f:
        f.write(failed_upscale_path + '\n')


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
            elif isinstance(msg, AddUpscaleJobInProgress):
                worker = Client.from_websocket(websocket)
                upscale_job = UpscaleJob(
                    src_file=msg.src_path, dest_file=msg.dest_path, pid=msg.pid, worker=worker)
                ChangeHandler.add_upscale_job(upscale_job)
                worker.add_upscale_job()
            elif isinstance(msg, UpscaleJobComplete):
                ChangeHandler.remove_upscale_job(msg.src_path)
                worker = Client.from_id(msg.worker_id)
                worker.upscale_job_finished()
                if msg.is_success:
                    if msg.src_path in failed_upscales:
                        del failed_upscales[msg.src_path]
                    logger.info(
                        f"Finished upscaling \"{msg.src_path}\". Wrote to {msg.dest_path}")
                    if worker != None and not worker.is_available():
                        logger.info(
                            f"Worker {msg.worker_id} is now accepting upscales.")
                        worker.set_availability(True)
                else:
                    failed_upscales[msg.src_path] = (
                        failed_upscales[msg.src_path] + 1) if msg.src_path in failed_upscales else 1
                    logger.info(
                        f"Upscale failed. Adding it back to the queue for another upscale attempt...")
                    if worker != None and worker.is_available():
                        logger.info(
                            f"Worker {msg.worker_id} will not be available until it has completed an upscale.")
                        worker.set_availability(False)
                    elif worker != None and worker.upscaling_tasks() == 0:
                        # If all upscales happened to fail, then it doesn't have anything going on right now. Then, it must be available.
                        worker.set_availability(True)
                    if os.path.exists(msg.src_path):
                        if failed_upscales[msg.src_path] < config.max_reattempts:
                            ChangeHandler.queue_upscale(msg.src_path)
                        else:
                            write_errored_upscale(msg.src_path)
                    else:
                        logger.error(
                            f"Could not find {msg.src_path}. Perhaps something deleted it, somehow?")
    except ConnectionClosed:
        logger.info(
            f"Worker {worker.id()} disconnected. (Remote IP: {worker.remote_address()})")

    finally:
        worker.unregister()
        if ChangeHandler.has_upscale_jobs(worker):
            logger.warning(
                f"Worker {worker.id()} has upscale jobs in progress. Due to the disconnection, the status of existing upscale jobs will no longer be synced so upscale jobs will be restarted")
            ChangeHandler.remove_upscale_jobs_of(worker)


async def main():
    if not os.path.exists(config.source):
        logger.error(
            f"A source directory containing all the non-upscaled content must exist. The path \"{config.source}\" does not exist.")
        return

    if not os.path.isdir(config.source):
        logger.error(f"\"{config.source}\" must be a directory.")
        return

    if not os.path.exists(config.upscaling):
        logger.error(
            f"An upscaling directory containing all WIP upscales must exist. The path \"{config.upscaling}\" does not exist."
        )
        return
    if not os.path.isdir(config.upscaling):
        logger.error(
            f"\"{config.upscaling}\" must be a directory."
        )
        return

    if not os.path.exists(config.upscaled):
        logger.error(
            f"An upscaled directory containing all all completed upscales must exist. The path \"{config.upscaled}\" does not exist."
        )
        return

    if not os.path.isdir(config.upscaling):
        logger.error(
            f"\"{config.upscaled}\" must be a directory."
        )
        return

    logger.info(f"Listening for changes in {config.source}")
    loop = asyncio.get_event_loop()

    event_handler = ChangeHandler(loop=loop)
    observer = Observer()
    observer.schedule(event_handler, config.source, recursive=True)
    observer_thread = threading.Thread(target=observer.start)
    queue_thread = threading.Thread(target=event_handler.queue_listener)
    observer_thread.daemon = True
    queue_thread.daemon = True
    observer_thread.start()
    queue_thread.start()

    async with serve(handler, "0.0.0.0", PORT) as server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
