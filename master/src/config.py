from pydantic import BaseModel


class Config(BaseModel):
    upscaling: str
    upscaled: str
    source: str
