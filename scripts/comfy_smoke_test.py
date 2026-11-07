"""Submit a minimal SD1.5 txt2img workflow to a running ComfyUI and save the image."""

import json
import sys
import time
import urllib.request
import uuid

BASE = "http://127.0.0.1:8188"
PROMPT = sys.argv[1] if len(sys.argv) > 1 else "a serene mountain lake at sunrise, soft mist, cinematic lighting"
OUT = sys.argv[2] if len(sys.argv) > 2 else "out.png"

workflow = {
    "3": {"class_type": "KSampler", "inputs": {
        "seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler",
        "scheduler": "normal", "denoise": 1.0, "model": ["4", 0],
        "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
    "4": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"}},
    "5": {"class_type": "EmptyLatentImage",
          "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "blurry, low quality, deformed", "clip": ["4", 1]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage",
          "inputs": {"filename_prefix": "berry_acceptance", "images": ["8", 0]}},
}

payload = json.dumps({"prompt": workflow, "client_id": uuid.uuid4().hex}).encode()
req = urllib.request.Request(f"{BASE}/prompt", data=payload,
                             headers={"Content-Type": "application/json"})
prompt_id = json.loads(urllib.request.urlopen(req).read())["prompt_id"]
print(f"queued prompt {prompt_id}")

started = time.time()
while time.time() - started < 600:
    history = json.loads(urllib.request.urlopen(f"{BASE}/history/{prompt_id}").read())
    if prompt_id in history:
        entry = history[prompt_id]
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            print("EXECUTION ERROR:", json.dumps(status)[:800])
            sys.exit(1)
        for node_output in entry.get("outputs", {}).values():
            for image in node_output.get("images", []):
                url = (f"{BASE}/view?filename={image['filename']}"
                       f"&subfolder={image.get('subfolder','')}&type={image['type']}")
                data = urllib.request.urlopen(url).read()
                with open(OUT, "wb") as handle:
                    handle.write(data)
                print(f"saved {OUT} ({len(data)} bytes) in {time.time()-started:.1f}s")
                sys.exit(0)
    time.sleep(2)

print("timed out waiting for the image")
sys.exit(1)
