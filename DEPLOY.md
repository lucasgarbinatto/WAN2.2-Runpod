# Deploy on RunPod Serverless

Repo layout (whole project pushed to GitHub):

```
Runpod/                    ← repo root
  Dockerfile               ← RunPod uses this
  wan-multi-ref-worker/      ← worker code (handler, workflows)
  app.py                   ← local UI (not deployed)
  generate_video.py        ← local CLI (not deployed)
```

## 1. RunPod GitHub settings

When creating the endpoint:

| Field | Value |
|-------|--------|
| Repository | your GitHub repo |
| Branch | `main` |
| **Dockerfile path** | `Dockerfile` |
| **Build context** | `/` (repo root) |

No network volume needed — models are baked into the image at build time.

## 2. Endpoint settings

- GPU: **A100 80GB** or **H100**
- Min workers: `0`, Max workers: `1`
- Idle timeout: `5` min
- **Execution timeout:** `3600000` (60 min)
- FlashBoot: **On**

First build takes **20–40 min** (downloads models). After that, workers start fast.

## 3. After deploy

Copy **Endpoint ID** from the RunPod console into `.env`:

```
RUNPOD_ENDPOINT_ID=your-endpoint-id
RUNPOD_API_KEY=rpa_your_key
```

## 4. Test (Requests tab) — Ingredients

```json
{
  "input": {
    "prompt": "character at the desk, papers rustle, gentle camera push-in",
    "character_image": "https://example.com/character-turnaround.png",
    "scene_image": "https://example.com/office-scene.png",
    "length": 81
  }
}
```

Legacy single-image still works:

```json
{
  "input": {
    "prompt": "gentle wind moves the hair",
    "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png",
    "length": 81
  }
}
```

## 5. Use locally

```powershell
python generate_video.py --character char.png --scene office.png --prompt "gentle camera push-in" --output out.mp4
python app.py
```

Push updates to GitHub, then **Redeploy** the endpoint in RunPod to rebuild.
