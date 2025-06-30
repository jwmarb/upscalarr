from pathlib import Path
from pydantic import BaseModel
import yaml
from .constants import CONFIG


class FoldersConfig(BaseModel):
    src: str
    work: str
    out: str


class ListenersConfig(BaseModel):
    ip: str
    port: int


class LogsConfig(BaseModel):
    failed: str


class MasterConfig(BaseModel):
    listener: ListenersConfig
    max_retries: int
    max_concurrent_tasks: int
    logs: LogsConfig
    allowed_extensions: list[str]


class MasterHostConfig(BaseModel):
    ip: str
    port: int


class WorkerConfig(BaseModel):
    video2x: str | dict[str, str]
    delete_on_completion: bool
    master_host: MasterHostConfig
    rename_output: bool


class Config(BaseModel):
    folders: list[FoldersConfig]
    master: MasterConfig
    worker: WorkerConfig

    def get_folder(self, src: str | Path):
        name = src if type(src) == str else str(src)
        for folder in self.folders:
            if folder.src == name:
                return folder
        return None


with open(CONFIG, "r") as f:
    raw = yaml.safe_load(f)
    config = Config(**raw)
