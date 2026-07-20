import base64
import binascii
import json
import logging
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import runpod
import websocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server_address = os.getenv("SERVER_ADDRESS", "127.0.0.1")
comfy_input_dir = os.getenv("COMFY_INPUT_DIR", "/ComfyUI/input")
client_id = str(uuid.uuid4())

DEFAULT_NEGATIVE = (
    "bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, "
    "images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, "
    "incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, "
    "misshapen limbs, fused fingers, still picture, messy background, three legs, many people "
    "in the background, walking backwards"
)


def to_nearest_multiple_of_16(value):
    numeric_value = float(value)
    adjusted = int(round(numeric_value / 16.0) * 16)
    return max(16, adjusted)


def snap_frames(value):
    """Wan expects frame counts of the form 4n+1."""
    frames = max(17, int(value))
    return ((frames - 1 + 3) // 4) * 4 + 1


def stage_image_for_comfy(local_path):
    """Copy image into ComfyUI's input folder; LoadImage only resolves names there."""
    os.makedirs(comfy_input_dir, exist_ok=True)
    basename = os.path.basename(local_path)
    staged_name = f"{uuid.uuid4().hex[:8]}_{basename}"
    staged_path = os.path.join(comfy_input_dir, staged_name)
    shutil.copy2(local_path, staged_path)
    return staged_name


def save_base64_to_file(base64_data, temp_dir, output_filename):
    if "," in base64_data and base64_data.startswith("data:"):
        base64_data = base64_data.split(",", 1)[1]
    decoded_data = base64.b64decode(base64_data)
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
    with open(file_path, "wb") as f:
        f.write(decoded_data)
    return file_path


def download_file_from_url(url, output_path):
    result = subprocess.run(["wget", "-O", output_path, "--no-verbose", url], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"URL download failed: {result.stderr}")
    return output_path


def resolve_image(item, temp_dir, filename):
    if item.startswith("http://") or item.startswith("https://"):
        path = os.path.join(temp_dir, filename)
        return download_file_from_url(item, path)
    return save_base64_to_file(item, temp_dir, filename)


def collect_ref_images(job_input, task_id):
    """Return list of local image paths from ref_images, ingredients, or legacy fields."""
    if "ref_images" in job_input and job_input["ref_images"]:
        paths = []
        for i, item in enumerate(job_input["ref_images"][:4]):
            paths.append(resolve_image(item, task_id, f"ref_{i}.jpg"))
        return paths

    # Ingredients: scene anchors frame 0, character guides CLIP appearance.
    character = job_input.get("character_image")
    scene = job_input.get("scene_image")
    if character or scene:
        if not character or not scene:
            raise ValueError("Ingredients mode requires both character_image and scene_image")
        return [
            resolve_image(scene, task_id, "scene.jpg"),
            resolve_image(character, task_id, "character.jpg"),
        ]

    if "image_path" in job_input:
        return [job_input["image_path"]]
    if "image_url" in job_input:
        return [resolve_image(job_input["image_url"], task_id, "input_image.jpg")]
    if "image_base64" in job_input:
        return [resolve_image(job_input["image_base64"], task_id, "input_image.jpg")]
    return []


def auto_ref_positions(n, length):
    if n <= 1:
        return ""
    if n == 2:
        return "0,1.0"
    ratios = [i / (n - 1) for i in range(n)]
    return ",".join(f"{r:.3f}" for r in ratios)


def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    data = json.dumps({"prompt": prompt, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI prompt rejected ({e.code}): {body}") from e


def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)["prompt_id"]
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message["type"] == "executing":
                data = message["data"]
                if data["node"] is None and data["prompt_id"] == prompt_id:
                    break

    history = get_history(prompt_id)[prompt_id]
    for node_id in history["outputs"]:
        node_output = history["outputs"][node_id]
        if "gifs" in node_output:
            videos = []
            for video in node_output["gifs"]:
                with open(video["fullpath"], "rb") as f:
                    videos.append(base64.b64encode(f.read()).decode("utf-8"))
            if videos:
                return videos[0]
    return None


def load_workflow(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def apply_common_settings(prompt, job_input, length, steps, mode):
    prompt["541"]["inputs"]["num_frames"] = length
    if mode == "keyframes" and "end_image" in prompt["541"]["inputs"]:
        prompt["541"]["inputs"]["fun_or_fl2v_model"] = True
    prompt["135"]["inputs"]["positive_prompt"] = job_input["prompt"]
    prompt["135"]["inputs"]["negative_prompt"] = job_input.get("negative_prompt", DEFAULT_NEGATIVE)
    prompt["220"]["inputs"]["seed"] = job_input.get("seed", 42)
    prompt["540"]["inputs"]["seed"] = job_input.get("seed", 42)
    prompt["540"]["inputs"]["cfg"] = job_input.get("cfg", 2.0)

    width = to_nearest_multiple_of_16(job_input.get("width", 480))
    height = to_nearest_multiple_of_16(job_input.get("height", 832))
    prompt["235"]["inputs"]["value"] = width
    prompt["236"]["inputs"]["value"] = height
    prompt["498"]["inputs"]["context_overlap"] = job_input.get("context_overlap", 48)
    prompt["498"]["inputs"]["context_frames"] = length

    if "834" in prompt:
        prompt["834"]["inputs"]["steps"] = steps
        prompt["829"]["inputs"]["step"] = int(steps * 0.6)


def configure_single(prompt, image_path):
    prompt["244"]["inputs"]["image"] = stage_image_for_comfy(image_path)


def configure_refonly(prompt, paths):
    """Blend all refs via CLIP vision; only the first image anchors frame 0."""
    n = len(paths)
    prompt["244"]["inputs"]["image"] = stage_image_for_comfy(paths[0])
    prompt["541"]["inputs"].pop("end_image", None)
    prompt["541"]["inputs"]["fun_or_fl2v_model"] = False

    if n == 1:
        prompt["193"]["inputs"]["image_1"] = ["171", 0]
        prompt["193"]["inputs"].pop("image_2", None)
        return

    if n > 1:
        prompt["620"]["inputs"]["image"] = stage_image_for_comfy(paths[1])
    if n > 2:
        prompt["621"]["inputs"]["image"] = stage_image_for_comfy(paths[2])
    if n > 3:
        prompt["617"]["inputs"]["image"] = stage_image_for_comfy(paths[3])

    prompt["193"]["inputs"].pop("image_2", None)
    if n == 2:
        prompt["193"]["inputs"]["image_1"] = ["624", 0]
    elif n == 3:
        prompt["193"]["inputs"]["image_1"] = ["625", 0]
    else:
        prompt["626"]["inputs"]["image1"] = ["625", 0]
        prompt["626"]["inputs"]["image2"] = ["613", 0]
        prompt["193"]["inputs"]["image_1"] = ["626", 0]


def pick_workflow(ref_count):
    if ref_count <= 1:
        return "/new_Wan22_api.json", "single"
    return "/new_Wan22_multiref_api.json", "refonly"


def handler(job):
    job_input = job.get("input", {})
    logger.info("job keys: %s", list(job_input.keys()))
    task_id = f"task_{uuid.uuid4()}"

    try:
        ref_paths = collect_ref_images(job_input, task_id)
    except ValueError as e:
        return {"error": str(e)}
    if not ref_paths:
        return {
            "error": (
                "No image provided. Use character_image+scene_image, "
                "ref_images, image_base64, image_url, or image_path."
            )
        }

    ref_count = len(ref_paths)
    workflow_file, mode = pick_workflow(ref_count)
    logger.info("mode=%s refs=%d workflow=%s", mode, ref_count, workflow_file)

    positions = job_input.get("ref_positions") or auto_ref_positions(ref_count, job_input.get("length", 81))
    logger.info("ref_positions=%s", positions)

    prompt = load_workflow(workflow_file)
    length = snap_frames(job_input.get("length", 81))
    steps = job_input.get("steps", 10)
    apply_common_settings(prompt, job_input, length, steps, mode)

    if mode == "single":
        configure_single(prompt, ref_paths[0])
    else:
        configure_refonly(prompt, ref_paths)

    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    http_url = f"http://{server_address}:8188/"

    for _ in range(180):
        try:
            urllib.request.urlopen(http_url, timeout=5)
            break
        except Exception:
            time.sleep(1)
    else:
        return {"error": "ComfyUI not reachable"}

    ws = websocket.WebSocket()
    for attempt in range(36):
        try:
            ws.connect(ws_url)
            break
        except Exception as e:
            if attempt == 35:
                return {"error": f"WebSocket failed: {e}"}
            time.sleep(5)

    try:
        video_b64 = get_videos(ws, prompt)
    except Exception as e:
        logger.exception("generation failed")
        return {"error": str(e)}
    finally:
        ws.close()

    if video_b64:
        return {"video": video_b64, "ref_count": ref_count, "ref_positions": positions}
    return {"error": "Video not found."}


runpod.serverless.start({"handler": handler})
