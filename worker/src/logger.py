import logging
import socket

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger()


def set_logger_worker_id(id: int):
    for handler in logger.handlers:
        handler.setFormatter(logging.Formatter(
            f"(Worker {id} [{socket.gethostbyname(socket.gethostname())}]) " + '%(asctime)s - %(levelname)s - %(message)s'))
    logger.info(f"Assigned as Worker {id}")
