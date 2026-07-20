# Deploy Wan2.2 Multi-Reference Serverless Worker

> **This repo is deployed from the root.** See [../DEPLOY.md](../DEPLOY.md) for RunPod setup.

Worker source files live in this folder; the root [Dockerfile](../Dockerfile) copies them into the image.

## Ingredients (recommended)

```json
{
  "input": {
    "prompt": "character at the desk, papers rustle, city lights outside, gentle camera push-in",
    "character_image": "https://example.com/character-turnaround.png",
    "scene_image": "https://example.com/office-scene.png",
    "width": 480,
    "height": 832,
    "length": 81,
    "steps": 10,
    "seed": 42,
    "cfg": 2.0
  }
}
```

`scene_image` anchors frame 0; `character_image` guides appearance via CLIP compose.

## Legacy multi-ref

```json
{
  "input": {
    "prompt": "person walks forward slowly, cinematic lighting",
    "ref_images": [
      "https://example.com/scene.png",
      "https://example.com/char.png"
    ],
    "ref_positions": "0,1.0",
    "width": 480,
    "height": 832,
    "length": 81,
    "steps": 10,
    "seed": 42,
    "cfg": 2.0
  }
}
```

## API contract

| Field | Description |
|-------|-------------|
| `character_image` + `scene_image` | Ingredients mode (base64 or URL). Both required together. Order resolved as `[scene, character]`. |
| `ref_images` | 1-4 images (base64 or URL). Wins over ingredients if both are sent. Legacy `image_base64` still works for 1 image. |
| `ref_positions` | Optional. `"0,0.5,1.0"` or `"0,40,80"`. Auto-distributed if omitted. |
| `prompt` | Motion / scene description |
| `length` | Frame count (default 81 = ~5s at 16fps) |

**Modes:**
- 1 ref -> standard I2V (image anchors frame 0)
- 2-4 refs / ingredients -> **compose mode**: all refs averaged in CLIP vision for appearance; first ref (scene) loosely anchors frame 0 (no end-frame morph)

`ref_positions` is echoed in the response for clients but is not used for temporal keyframes in compose mode. For timeline keyframe control, Wan22FMLF nodes are installed in the image for a future upgrade.

## Test request (RunPod Requests tab)

Update `.env`:

```
RUNPOD_ENDPOINT_ID=your-new-endpoint-id
RUNPOD_API_KEY=your-api-key
```
