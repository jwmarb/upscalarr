import os

MASTER_IP = os.environ.get("MASTER_IP", "0.0.0.0")
MASTER_PORT = os.environ.get("MASTER_PORT", "8765")
CONFIG = os.environ.get("CONFIG_PATH", "config.yaml")
