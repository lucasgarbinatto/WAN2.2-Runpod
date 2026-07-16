import copy
import json
from pathlib import Path

base = json.loads(Path("new_Wan22_flf2v_api.json").read_text(encoding="utf-8"))
wf = copy.deepcopy(base)
wf["620"] = {"inputs": {"image": "ref1.png"}, "class_type": "LoadImage", "_meta": {"title": "ref1"}}
wf["621"] = {"inputs": {"image": "ref2.png"}, "class_type": "LoadImage", "_meta": {"title": "ref2"}}
wf["622"] = {
    "inputs": {
        "width": ["235", 0],
        "height": ["236", 0],
        "upscale_method": "lanczos",
        "keep_proportion": "crop",
        "pad_color": "0, 0, 0",
        "crop_position": "center",
        "divisible_by": 2,
        "device": "cpu",
        "per_batch": 0,
        "image": ["620", 0],
    },
    "class_type": "ImageResizeKJv2",
    "_meta": {"title": "resize ref1"},
}
wf["623"] = {
    "inputs": {
        "width": ["235", 0],
        "height": ["236", 0],
        "upscale_method": "lanczos",
        "keep_proportion": "crop",
        "pad_color": "0, 0, 0",
        "crop_position": "center",
        "divisible_by": 2,
        "device": "cpu",
        "per_batch": 0,
        "image": ["621", 0],
    },
    "class_type": "ImageResizeKJv2",
    "_meta": {"title": "resize ref2"},
}
wf["624"] = {"inputs": {"image1": ["171", 0], "image2": ["622", 0]}, "class_type": "ImageBatch", "_meta": {"title": "batch 0+1"}}
wf["625"] = {"inputs": {"image1": ["624", 0], "image2": ["623", 0]}, "class_type": "ImageBatch", "_meta": {"title": "batch +2"}}
wf["626"] = {"inputs": {"image1": ["625", 0], "image2": ["613", 0]}, "class_type": "ImageBatch", "_meta": {"title": "batch +end"}}
wf["193"]["inputs"]["image_1"] = ["626", 0]
wf["193"]["inputs"].pop("image_2", None)
Path("new_Wan22_multiref_api.json").write_text(json.dumps(wf, indent=2), encoding="utf-8")
print("ok", len(wf))
