from shared.message import MessageType, RegisterWorker, UpscaleFailed, parse_message, ReceiveUpscaling

mock_json_obj = "{\"type\":\"" + \
    str(MessageType.REGISTER_WORKER) + "\",\"sender\":\"worker\"}"


def test_register_worker_serialization():
    data = RegisterWorker(type=MessageType.REGISTER_WORKER)
    assert data.type is MessageType.REGISTER_WORKER
    assert data.serialize() == mock_json_obj


def test_register_worker_deserialization():
    assert RegisterWorker.model_validate_json(mock_json_obj) == RegisterWorker(
        type=MessageType.REGISTER_WORKER)
    assert parse_message(mock_json_obj) == RegisterWorker(
        type=MessageType.REGISTER_WORKER)


def test_receive_upscaling_serialization_deserialization():
    files = ["foo.png", "bar.png"]
    json_msg = '{"type":"RECV_UPSCALING","files":["foo.png","bar.png"],"sender":"worker"}'
    data2 = parse_message(json_msg)
    assert data2 == ReceiveUpscaling(
        type=MessageType.RECV_UPSCALING, files=files, sender="worker")
    assert ReceiveUpscaling.model_validate_json(json_msg) == ReceiveUpscaling(
        type=MessageType.RECV_UPSCALING, files=files, sender="worker")
    assert ReceiveUpscaling(type=MessageType.RECV_UPSCALING,
                            files=files, sender="worker").serialize() == json_msg


def test_upscale_failed_serialization_deserialization():
    json_msg = '{"type":"UPSCALE_FAILED","reason":"bad/file/path.png","code":42,"sender":"worker"}'
    # Serialization
    assert UpscaleFailed(type=MessageType.UPSCALE_FAILED,
                         reason="bad/file/path.png", code=42, sender="worker").serialize() == json_msg
    # Deserialization
    assert UpscaleFailed.model_validate_json(json_msg) == UpscaleFailed(
        type=MessageType.UPSCALE_FAILED, reason="bad/file/path.png", code=42, sender="worker"
    )
    assert parse_message(json_msg) == UpscaleFailed(
        type=MessageType.UPSCALE_FAILED, reason="bad/file/path.png", code=42, sender="worker")
