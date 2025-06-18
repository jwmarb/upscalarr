from pydantic import BaseModel
import yaml
from .constants import CONFIG


class Config(BaseModel):
    upscaling: str
    upscaled: str
    source: str
    cmd: str


with open(CONFIG, "r") as f:
    raw = yaml.safe_load(f)
    config = Config(**raw)
