"""Smoke tests for multi-ref payload building (no API calls)."""

from generate_video import auto_ref_positions, build_input_data


def test_single_image_legacy():
    data = build_input_data(["test_pixel.png"], "walk", length=81)
    assert "image_base64" in data
    assert "ref_images" not in data


def test_multi_ref_payload_shape():
    # encode_image will fail on missing file - test auto_ref_positions only
    assert auto_ref_positions(3) == "0.000,0.500,1.000"
    assert auto_ref_positions(4) == "0.000,0.333,0.667,1.000"
    assert auto_ref_positions(2) == "0,1.0"


def test_workflow_json_valid():
    import json
    from pathlib import Path

    wf_dir = Path(__file__).parent / "wan-multi-ref-worker"
    for name in ("new_Wan22_api.json", "new_Wan22_flf2v_api.json", "new_Wan22_multiref_api.json"):
        data = json.loads((wf_dir / name).read_text(encoding="utf-8"))
        assert "541" in data
        assert "131" in data


if __name__ == "__main__":
    test_single_image_legacy()
    test_multi_ref_payload_shape()
    test_workflow_json_valid()
    print("all ok")
