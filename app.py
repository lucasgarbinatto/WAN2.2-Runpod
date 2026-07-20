#!/usr/bin/env python3
"""Gradio UI: character + scene ingredients → video."""

import os
import tempfile
import uuid

import gradio as gr
from dotenv import load_dotenv

from generate_video import (
    FPS,
    build_ingredients_input,
    save_video,
    submit_job,
    wait_for_completion,
)

load_dotenv()


def _path_from_file(f) -> str | None:
    if not f:
        return None
    if isinstance(f, str):
        return f
    if hasattr(f, "name"):
        return f.name
    return str(f)


def generate(
    character_file,
    scene_file,
    prompt: str,
    duration: float,
    progress=gr.Progress(track_tqdm=False),
):
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")
    api_key = os.getenv("RUNPOD_API_KEY")
    if not endpoint_id or not api_key:
        raise gr.Error("Missing RUNPOD_ENDPOINT_ID or RUNPOD_API_KEY in .env")
    if not prompt or not prompt.strip():
        raise gr.Error("Write a prompt")

    character_path = _path_from_file(character_file)
    scene_path = _path_from_file(scene_file)
    if not character_path or not scene_path:
        raise gr.Error("Drop both a character reference and a scene reference")

    length = int(duration * FPS)

    progress(0.1, desc="Encoding character + scene...")
    input_data = build_ingredients_input(
        character_path,
        scene_path,
        prompt.strip(),
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


with gr.Blocks(title="WAN Ingredients Video") as demo:
    gr.Markdown("# WAN Ingredients Video")
    gr.Markdown(
        "**Character** guides appearance (turnaround / close-up). "
        "**Scene** anchors the opening frame (environment). "
        "Describe motion and action in the prompt."
    )
    with gr.Row():
        with gr.Column():
            character = gr.File(
                label="Character reference",
                file_types=["image"],
                type="filepath",
            )
            scene = gr.File(
                label="Scene reference",
                file_types=["image"],
                type="filepath",
            )
            prompt = gr.Textbox(
                label="Prompt",
                placeholder="character at the desk, papers rustle, gentle camera push-in",
                lines=3,
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
        inputs=[character, scene, prompt, duration],
        outputs=video,
    )


if __name__ == "__main__":
    demo.launch()
