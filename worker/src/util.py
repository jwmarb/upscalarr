from worker.src.logger import set_logger_worker_id


class Worker:
    _worker_id: int | None = None

    @staticmethod
    def set_worker_id(id: int):
        set_logger_worker_id(id)
        Worker._worker_id = id

    @staticmethod
    def id():
        return Worker._worker_id
