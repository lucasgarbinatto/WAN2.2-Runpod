"""Repo-root shim so RunPod's GitHub scanner finds runpod.serverless.start()."""
import importlib.util
from pathlib import Path

_path = Path(__file__).parent / "wan-multi-ref-worker" / "handler.py"
_spec = importlib.util.spec_from_file_location("worker_handler", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # defines handler + calls runpod.serverless.start()
