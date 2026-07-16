# Deploy Wan2.2 Multi-Reference Serverless Worker

> **This repo is deployed from the root.** See [../DEPLOY.md](../DEPLOY.md) for RunPod setup.

Worker source files live in this folder; the root [Dockerfile](../Dockerfile) copies them into the image.

```json
{
  "input": {
    "prompt": "person walks forward slowly, cinematic lighting",
    "ref_images": [
      "https://example.com/char.png",
      "https://example.com/outfit.png",
      "https://example.com/scene.png"
    ],
    "ref_positions": "0,0.5,1.0",
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
| `ref_images` | 1-4 images (base64 or URL). Legacy `image_base64` still works for 1 image. |
| `ref_positions` | Optional. `"0,0.5,1.0"` or `"0,40,80"`. Auto-distributed if omitted. |
| `prompt` | Motion / scene description |
| `length` | Frame count (default 81 = ~5s at 16fps) |

**Modes:**
- 1 ref -> standard I2V
- 2 refs -> first/last frame (FLF2V)
- 3-4 refs -> all refs blended in CLIP vision; first=start frame, last=end frame

`ref_positions` is recorded in the response for your client; temporal placement uses first/last frames with middle refs affecting appearance via CLIP blending. Full Wan22FMLF timeline control requires a future workflow upgrade (nodes are installed in the image).

## Test request (RunPod Requests tab)

Update `.env`:

```
RUNPOD_ENDPOINT_ID=your-new-endpoint-id
RUNPOD_API_KEY=your-api-key
```
