"""Smoke tests for multi-ref / ingredients payload building (no API calls)."""

import base64
import importlib.util
import tempfile
from pathlib import Path

from generate_video import auto_ref_positions, build_ingredients_input, build_input_data

# Tiny 1x1 PNG
_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

_HANDLER_PATH = Path(__file__).parent / "wan-multi-ref-worker" / "handler.py"


def _load_handler():
    import sys
    from unittest.mock import MagicMock

    sys.modules.setdefault("runpod", MagicMock())
    sys.modules.setdefault("websocket", MagicMock())
    spec = importlib.util.spec_from_file_location("wan_handler", _HANDLER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_single_image_legacy():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(_PIXEL)
        path = f.name
    try:
        data = build_input_data([path], "walk", length=81)
        assert "image_base64" in data
        assert "ref_images" not in data
    finally:
        Path(path).unlink(missing_ok=True)


def test_multi_ref_payload_shape():
    assert auto_ref_positions(3) == "0.000,0.500,1.000"
    assert auto_ref_positions(4) == "0.000,0.333,0.667,1.000"
    assert auto_ref_positions(2) == "0,1.0"


def test_ingredients_order_scene_then_character():
    with tempfile.TemporaryDirectory() as tmp:
        scene = Path(tmp) / "scene.png"
        character = Path(tmp) / "character.png"
        scene.write_bytes(_PIXEL + b"SCENE")
        character.write_bytes(_PIXEL + b"CHAR")
        data = build_ingredients_input(str(character), str(scene), "walk", length=81)
        assert "ref_images" in data
        assert len(data["ref_images"]) == 2
        # First encoded blob is scene (frame-0 anchor), second is character.
        assert data["ref_images"][0] == base64.b64encode(scene.read_bytes()).decode()
        assert data["ref_images"][1] == base64.b64encode(character.read_bytes()).decode()


def test_handler_ingredients_aliases():
    handler = _load_handler()
    scene_b64 = base64.b64encode(_PIXEL + b"SCENE").decode()
    char_b64 = base64.b64encode(_PIXEL + b"CHAR").decode()
    with tempfile.TemporaryDirectory() as tmp:
        paths = handler.collect_ref_images(
            {"character_image": char_b64, "scene_image": scene_b64},
            tmp,
        )
        assert len(paths) == 2
        assert Path(paths[0]).name == "scene.jpg"
        assert Path(paths[1]).name == "character.jpg"
        assert Path(paths[0]).read_bytes() == _PIXEL + b"SCENE"
        assert Path(paths[1]).read_bytes() == _PIXEL + b"CHAR"


def test_handler_ref_images_beats_ingredients():
    handler = _load_handler()
    only = base64.b64encode(_PIXEL + b"ONLY").decode()
    with tempfile.TemporaryDirectory() as tmp:
        paths = handler.collect_ref_images(
            {
                "ref_images": [only],
                "character_image": base64.b64encode(_PIXEL + b"CHAR").decode(),
                "scene_image": base64.b64encode(_PIXEL + b"SCENE").decode(),
            },
            tmp,
        )
        assert len(paths) == 1
        assert Path(paths[0]).read_bytes() == _PIXEL + b"ONLY"


def test_handler_ingredients_requires_both():
    handler = _load_handler()
    try:
        handler.collect_ref_images({"character_image": "x"}, "task_x")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "both" in str(e).lower()


def test_workflow_json_valid():
    import json

    wf_dir = Path(__file__).parent / "wan-multi-ref-worker"
    for name in ("new_Wan22_api.json", "new_Wan22_flf2v_api.json", "new_Wan22_multiref_api.json"):
        data = json.loads((wf_dir / name).read_text(encoding="utf-8"))
        assert "541" in data
        assert "131" in data


if __name__ == "__main__":
    test_single_image_legacy()
    test_multi_ref_payload_shape()
    test_ingredients_order_scene_then_character()
    test_handler_ingredients_aliases()
    test_handler_ref_images_beats_ingredients()
    test_handler_ingredients_requires_both()
    test_workflow_json_valid()
    print("all ok")
