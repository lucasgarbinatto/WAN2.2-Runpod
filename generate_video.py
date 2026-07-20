#!/usr/bin/env python3
"""Send image(s) to a RunPod Wan2.2 serverless endpoint and save the MP4."""

import argparse
import base64
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL = 10
MAX_WAIT = 1800  # 30 minutes
FPS = 16


def snap_frames(value: int) -> int:
    """Wan expects frame counts of the form 4n+1."""
    frames = max(17, int(value))
    return ((frames - 1 + 3) // 4) * 4 + 1


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def auto_ref_positions(n: int) -> str:
    if n <= 1:
        return ""
    if n == 2:
        return "0,1.0"
    return ",".join(f"{i / (n - 1):.3f}" for i in range(n))


def build_input_data(
    image_paths: list[str],
    prompt: str,
    *,
    negative_prompt: str | None = None,
    ref_positions: str | None = None,
    width: int = 480,
    height: int = 832,
    length: int = 81,
    steps: int = 10,
    seed: int = 42,
    cfg: float = 2.0,
) -> dict:
    if not image_paths:
        raise ValueError("At least one image is required")

    if len(image_paths) == 1:
        input_data = {
            "image_base64": encode_image(image_paths[0]),
            "prompt": prompt,
            "width": width,
            "height": height,
            "length": length,
            "steps": steps,
            "seed": seed,
            "cfg": cfg,
        }
    else:
        input_data = {
            "ref_images": [encode_image(p) for p in image_paths[:4]],
            "ref_positions": ref_positions or auto_ref_positions(len(image_paths)),
            "prompt": prompt,
            "width": width,
            "height": height,
            "length": length,
            "steps": steps,
            "seed": seed,
            "cfg": cfg,
        }

    if negative_prompt:
        input_data["negative_prompt"] = negative_prompt
    input_data["length"] = snap_frames(input_data["length"])
    return input_data


def build_ingredients_input(
    character_path: str,
    scene_path: str,
    prompt: str,
    **kwargs,
) -> dict:
    """Ingredients mode: scene anchors frame 0, character guides appearance via CLIP."""
    if not character_path or not scene_path:
        raise ValueError("Both character_path and scene_path are required")
    # Order matters for the worker: first ref = frame-0 anchor, second = CLIP compose.
    return build_input_data([scene_path, character_path], prompt, **kwargs)


def submit_job(endpoint_id: str, api_key: str, input_data: dict) -> str:
    url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json={"input": input_data}, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data.get("id")
    if not job_id:
        raise RuntimeError(f"No job id in response: {data}")
    return job_id


def wait_for_completion(endpoint_id: str, api_key: str, job_id: str) -> dict:
    url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    start = time.time()

    while time.time() - start < MAX_WAIT:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")

        if status == "COMPLETED":
            return data
        if status == "FAILED":
            raise RuntimeError(f"Job failed: {data.get('error', 'unknown error')}")
        if status in ("IN_QUEUE", "IN_PROGRESS"):
            elapsed = int(time.time() - start)
            print(f"  [{status}] waiting... ({elapsed}s)", flush=True)
            time.sleep(POLL_INTERVAL)
        else:
            raise RuntimeError(f"Unexpected status: {status} — {data}")

    raise TimeoutError(f"Timed out after {MAX_WAIT}s. Check job in console: {job_id}")


def save_video(output: dict, path: str) -> None:
    video_b64 = output.get("video")
    if not video_b64:
        raise RuntimeError(f"No video in output: {output}")

    if "," in video_b64 and video_b64.startswith("data:"):
        video_b64 = video_b64.split(",", 1)[1]

    raw = base64.b64decode(video_b64)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a video from image(s) via RunPod Wan2.2 serverless."
    )
    parser.add_argument("--image", help="Single input image (legacy)")
    parser.add_argument("--ref-images", nargs="+", help="Multiple reference images (2-4)")
    parser.add_argument("--character", help="Character reference image (ingredients mode)")
    parser.add_argument("--scene", help="Scene / opening-frame reference (ingredients mode)")
    parser.add_argument("--ref-positions", default=None, help='e.g. "0,0.5,1.0"')
    parser.add_argument("--prompt", required=True, help="Motion / scene description")
    parser.add_argument("--output", default="output.mp4", help="Output MP4 path")
    parser.add_argument("--negative-prompt", default=None)
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=832)
    parser.add_argument("--duration", type=float, default=None, help="Seconds (overrides --length)")
    parser.add_argument("--length", type=int, default=None, help="Frame count")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg", type=float, default=2.0)
    args = parser.parse_args()

    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    api_key = os.getenv("RUNPOD_API_KEY")
    if not endpoint_id or not api_key:
        print("Missing RUNPOD_ENDPOINT_ID or RUNPOD_API_KEY in .env", file=sys.stderr)
        return 1

    ingredients = bool(args.character or args.scene)
    if ingredients and not (args.character and args.scene):
        print("Ingredients mode requires both --character and --scene", file=sys.stderr)
        return 1

    if ingredients:
        image_paths = [args.scene, args.character]
    elif args.ref_images:
        image_paths = args.ref_images
    elif args.image:
        image_paths = [args.image]
    else:
        print("Provide --character/--scene, --ref-images, or --image", file=sys.stderr)
        return 1

    for p in image_paths:
        if not os.path.isfile(p):
            print(f"Image not found: {p}", file=sys.stderr)
            return 1

    length = snap_frames(args.length if args.length is not None else int((args.duration or 5) * FPS))
    common = dict(
        negative_prompt=args.negative_prompt,
        ref_positions=args.ref_positions,
        width=args.width,
        height=args.height,
        length=length,
        steps=args.steps,
        seed=args.seed,
        cfg=args.cfg,
    )

    print(f"Encoding {len(image_paths)} image(s)...")
    if ingredients:
        input_data = build_ingredients_input(args.character, args.scene, args.prompt, **common)
    else:
        input_data = build_input_data(image_paths, args.prompt, **common)

    print("Submitting job...")
    job_id = submit_job(endpoint_id, api_key, input_data)
    print(f"Job ID: {job_id}")

    print("Waiting for completion...")
    result = wait_for_completion(endpoint_id, api_key, job_id)

    print(f"Saving to {args.output}...")
    save_video(result.get("output") or {}, args.output)
    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    print(f"Done: {args.output} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
