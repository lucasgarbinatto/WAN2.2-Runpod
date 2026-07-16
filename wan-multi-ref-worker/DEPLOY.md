# Deploy Wan2.2 Multi-Reference Serverless Worker

## 1. Push this folder to GitHub

```bash
cd wan-multi-ref-worker
git init
git add .
git commit -m "Wan2.2 multi-ref serverless worker"
git remote add origin YOUR_REPO_URL
git push -u origin main
```

## 2. Network volume (optional)

Skip this for the same fast cold starts as the Hub template — models are baked into the Docker image at build time.

Only add a volume if you want to store extra LoRAs or large assets without rebuilding the image.

## 3. Create Serverless Endpoint

1. RunPod Console -> Serverless -> **New Endpoint**
2. Source: **GitHub** -> select your repo (`wan-multi-ref-worker/`)
3. Attach network volume only if you use one (optional)
4. GPU: **A100 80GB** or **H100** (A6000 48GB may work with fp8)
5. Settings:
   - Max workers: 1-3
   - Idle timeout: 5-10 min
   - **Execution timeout: 3600000** (60 min)
   - Flashboot: enabled
6. Build and deploy — **first build takes 20-40 min** (downloads ~40GB models into the image). After that, workers start fast like the Hub template.

## 4. Test request (RunPod Requests tab)

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

## 5. Point your local client at the new endpoint

Update `.env`:

```
RUNPOD_ENDPOINT_ID=your-new-endpoint-id
RUNPOD_API_KEY=your-api-key
```
