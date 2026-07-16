#!/usr/bin/env python3
"""Gradio UI: drop reference images, write prompt, watch the video."""

import os
import tempfile
import uuid

import gradio as gr
from dotenv import load_dotenv

from generate_video import (
    FPS,
    build_input_data,
    save_video,
    submit_job,
    wait_for_completion,
)

load_dotenv()


def _paths_from_gallery(files) -> list[str]:
    if not files:
        return []
    out = []
    for f in files:
        if isinstance(f, str):
            out.append(f)
        elif hasattr(f, "name"):
            out.append(f.name)
        else:
            out.append(str(f))
    return out


def generate(
    gallery_files,
    prompt: str,
    duration: float,
    ref_positions: str,
    progress=gr.Progress(track_tqdm=False),
):
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    api_key = os.getenv("RUNPOD_API_KEY")
    if not endpoint_id or not api_key:
        raise gr.Error("Missing RUNPOD_ENDPOINT_ID or RUNPOD_API_KEY in .env")
    if not prompt or not prompt.strip():
        raise gr.Error("Write a prompt")

    image_paths = _paths_from_gallery(gallery_files)
    if not image_paths:
        raise gr.Error("Drop at least one reference image")

    length = int(duration * FPS)
    positions = ref_positions.strip() or None

    progress(0.1, desc=f"Encoding {len(image_paths)} image(s)...")
    input_data = build_input_data(
        image_paths,
        prompt.strip(),
        ref_positions=positions,
        length=length,
    )

    progress(0.2, desc="Submitting job...")
    job_id = submit_job(endpoint_id, api_key, input_data)

    progress(0.3, desc=f"Generating ~{duration:.0f}s ({length} frames)...")
    result = wait_for_completion(endpoint_id, api_key, job_id)

    out_path = os.path.join(tempfile.gettempdir(), f"wan_{uuid.uuid4().hex}.mp4")
    progress(0.9, desc="Saving video...")
    save_video(result.get("output") or {}, out_path)
    progress(1.0, desc="Done")
    return out_path


with gr.Blocks(title="WAN Multi-Ref Video") as demo:
    gr.Markdown("# WAN Multi-Reference Video")
    gr.Markdown("Drop 1-4 reference images. First = start frame, last = end frame. All refs blend appearance.")
    with gr.Row():
        with gr.Column():
            gallery = gr.File(
                label="Reference images (1-4)",
                file_count="multiple",
                file_types=["image"],
                type="filepath",
            )
            prompt = gr.Textbox(
                label="Prompt",
                placeholder="person walks forward slowly, soft lighting",
                lines=3,
            )
            ref_positions = gr.Textbox(
                label="Ref positions (optional)",
                placeholder="0,0.5,1.0  — leave empty for auto",
            )
            duration = gr.Slider(
                minimum=3,
                maximum=30,
                value=5,
                step=1,
                label="Duration (seconds)",
            )
            btn = gr.Button("Generate", variant="primary")
        with gr.Column():
            video = gr.Video(label="Result", height=400)

    btn.click(
        fn=generate,
        inputs=[gallery, prompt, duration, ref_positions],
        outputs=video,
    )


if __name__ == "__main__":
    demo.launch()
