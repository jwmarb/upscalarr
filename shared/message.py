from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field, TypeAdapter, field_serializer
from enum import Enum, auto
import json

Sender = Literal["master", "worker"]


class EnumSerializer:
    @field_serializer("type")
    def serialize_message_type(self, message_type):
        # If the field is an Enum, serialize its name, else return as is
        return message_type.name if isinstance(message_type, Enum) else message_type


class SerializableBaseModel(BaseModel):
    @classmethod
    def _coerce_type_enum(cls, v):
        # Accept either the Enum value or its name (as string)
        if isinstance(v, MessageType):
            return v
        if isinstance(v, str):
            try:
                return MessageType[v]
            except KeyError:
                pass
        raise ValueError(f"Invalid type for {cls.__name__}: {v}")

    @classmethod
    def model_validate_json(cls, json_data):
        data = json.loads(json_data)
        if "type" in data:
            data["type"] = cls._coerce_type_enum(data["type"])
        return super().model_validate(data)

    def serialize(self) -> str:
        return self.model_dump_json()


class MessageType(Enum):
    REGISTER_WORKER = auto()
    RECV_UPSCALING = auto()
    UPSCALE_FAILED = auto()

    def __str__(self):
        return self.name


class ReceiveUpscaling(EnumSerializer, SerializableBaseModel):
    type: Literal[MessageType.RECV_UPSCALING] = MessageType.RECV_UPSCALING
    files: list[str]  # list of files being upscaled
    sender: Sender


class RegisterWorker(EnumSerializer, SerializableBaseModel):
    type: Literal[MessageType.REGISTER_WORKER] = MessageType.REGISTER_WORKER
    sender: Sender
    worker_id: int | None = None


class UpscaleFailed(EnumSerializer, SerializableBaseModel):
    type: Literal[MessageType.UPSCALE_FAILED] = MessageType.UPSCALE_FAILED
    path: str  # path to the file that failed
    code: int  # os error code
    sender: Sender = "worker"


Message = Annotated[Union[RegisterWorker, ReceiveUpscaling,
                          UpscaleFailed], Field(discriminator="type")]


def parse_message(msg_json_str: str):
    data = json.loads(msg_json_str)

    if isinstance(data, dict) and "type" in data:
        t = data["type"]
        if isinstance(t, str):
            try:
                data["type"] = MessageType[t]
            except KeyError:
                pass
    return TypeAdapter(Message).validate_python(data)
