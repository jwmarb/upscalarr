import logging
import socket

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger()


def set_worker_id(worker_id: int):
    for handler in logger.handlers:
        handler.setFormatter(logging.Formatter(
            f"(Worker {worker_id} [{socket.gethostbyname(socket.gethostname())}]) " + '%(asctime)s - %(levelname)s - %(message)s'))
    logger.info(f"Assigned as Worker {worker_id}")
