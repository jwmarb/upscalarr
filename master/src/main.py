import asyncio
import threading
from websockets.asyncio.server import serve
from websockets import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol
from master.src.client import Client
from master.src.logger import logger
from master.src.changehandler import ChangeHandler, UpscaleJob
from watchdog.observers import Observer
from shared.config import config
from shared.message import AddUpscaleJobInProgress, RegisterWorker, UpscaleJobComplete, parse_message
import os

failed_upscales: dict[str, int] = {}


def write_errored_upscale(failed_upscale_path: str):
    logger.warning(
        f"{failed_upscale_path} has reattempted {config.master.max_retries} times but failed all of them. It will be skipped!")
    with open(config.master.logs.failed, 'a' if os.path.exists(config.master.logs.failed) else 'w') as f:
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
                worker = Client.from_id(msg.worker_id)
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
                    logger.error(
                        f"Upscale for {msg.src_path} failed. Adding it back to the queue for another upscale attempt...")
                    if worker != None and worker.is_available() and worker.upscaling_tasks() > 0:
                        logger.info(
                            f"Worker {msg.worker_id} will not be available until it has completed an upscale.")
                        worker.set_availability(False)
                    elif worker != None and worker.upscaling_tasks() == 0:
                        # If all upscales happened to fail, then it doesn't have anything going on right now. Then, it must be available.
                        worker.set_availability(True)
                    if os.path.exists(msg.src_path):
                        if failed_upscales[msg.src_path] < config.master.max_retries:
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
                f"Worker {worker.id()} has upscale jobs in progress. Due to the disconnection, manual intervention would be required to stop the upscales, if they are still running.")
            ChangeHandler.remove_upscale_jobs_of(worker)


async def main():
    for folder in config.folders:
        if not os.path.exists(folder.src):
            logger.error(
                f"A source directory containing all the non-upscaled content must exist. The path \"{folder.src}\" does not exist.")
            return

        if not os.path.isdir(folder.src):
            logger.error(f"\"{folder.src}\" must be a directory.")
            return

    loop = asyncio.get_event_loop()
    event_handler = ChangeHandler(loop=loop)
    for folder in config.folders:
        logger.info(f"Listening for changes in {folder.src}")

        observer = Observer()
        observer.schedule(event_handler, folder.src, recursive=True)
        observer_thread = threading.Thread(target=observer.start)
        observer_thread.daemon = True
        observer_thread.start()
    queue_thread = threading.Thread(target=event_handler.queue_listener)
    queue_thread.daemon = True
    queue_thread.start()

    async with serve(handler, config.master.listener.ip, config.master.listener.port) as server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
