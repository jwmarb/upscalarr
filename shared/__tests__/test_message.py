import pytest
from shared.message import (
    MessageType,
    UpscaleJobComplete,
    AddUpscaleJobInProgress,
    AddUpscaleJob,
    SourceModifiedOrDeleted,
    RegisterWorker,
    UpscaleFailed,
    parse_message,
)


def test_serialize_and_deserialize_upscale_job_complete():
    message = UpscaleJobComplete(
        is_success=True, worker_id=1, dest_path="/dst", src_path="/src")
    serialized = message.serialize()
    deserialized = UpscaleJobComplete.model_validate_json(serialized)
    assert deserialized == message
    data = message.model_dump()
    assert data["type"] == str(MessageType.UPSCALE_JOB_COMPLETE)


def test_add_upscale_job_in_progress():
    msg = AddUpscaleJobInProgress(
        src_path="src", dest_path="dst", worker_id=42, pid=999)
    json_data = msg.serialize()
    loaded = AddUpscaleJobInProgress.model_validate_json(json_data)
    assert loaded.src_path == "src"
    assert loaded.type == MessageType.ADD_UPSCALE_JOB_IN_PROGRESS


def test_register_worker_with_and_without_id():
    msg = RegisterWorker(sender="worker", worker_id=12)
    json_data = msg.serialize()
    loaded = RegisterWorker.model_validate_json(json_data)
    assert loaded.worker_id == 12

    # Without worker_id
    msg2 = RegisterWorker(sender="worker")
    assert msg2.worker_id is None


def test_upscale_failed_serialization():
    msg = UpscaleFailed(path="failpath", code=2)
    data = msg.model_dump()
    assert data["type"] == str(MessageType.UPSCALE_FAILED)
    js = msg.serialize()
    re = UpscaleFailed.model_validate_json(js)
    assert re.path == "failpath"
    assert re.code == 2


@pytest.mark.parametrize("msg_cls, kwargs", [
    (AddUpscaleJob, {"file": "f", "sender": "master"}),
    (SourceModifiedOrDeleted, {"file": "g", "sender": "master"}),
])
def test_other_messages(msg_cls, kwargs):
    msg = msg_cls(**kwargs)
    json_data = msg.serialize()
    loaded = msg_cls.model_validate_json(json_data)
    for k, v in kwargs.items():
        assert getattr(loaded, k) == v
    assert loaded.type == msg.type


def test_type_accepts_enum_name_str():
    json_data = '{"type": "UPSCALE_JOB_COMPLETE", "is_success": false, "worker_id": 1, "dest_path": "d", "src_path": "s", "sender":"worker"}'
    obj = UpscaleJobComplete.model_validate_json(json_data)
    assert obj.type == MessageType.UPSCALE_JOB_COMPLETE


def test_parse_message_with_enum_name():
    json_data = '{"type": "REGISTER_WORKER", "sender": "worker"}'
    msg = parse_message(json_data)
    assert isinstance(msg, RegisterWorker)
    assert msg.type == MessageType.REGISTER_WORKER


def test_parse_message_with_enum_value_direct():
    data = RegisterWorker(sender="worker", worker_id=5)
    serialized = data.serialize()
    parsed = parse_message(serialized)
    assert isinstance(parsed, RegisterWorker)
    assert parsed.worker_id == 5


def test_invalid_type_raises_valueerror():
    bad_json = '{"type": "NOT_A_REAL_TYPE", "sender": "worker"}'
    with pytest.raises(ValueError):
        RegisterWorker.model_validate_json(bad_json)
