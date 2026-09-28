import os
import time
import re
import gc
from pathlib import Path
from PIL import Image

MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
ADAPTER_DIR = Path("app/ai/lora_adapter_rs")

_MODEL = None
_PROCESSOR = None


def is_local_vlm_enabled() -> bool:
    """
    Check if local deep-learning VLM execution is permitted in the current runtime.
    - Explicit override via ENABLE_LOCAL_VLM takes highest priority ("true" / "false").
    - If running on Render (RENDER=true or RENDER_SERVICE_ID present), automatically disabled
      to protect Render's 512 MB RAM limit.
    - Otherwise (local workstation / GPU / Docker), enabled by default.
    """
    override = os.getenv("ENABLE_LOCAL_VLM")
    if override is not None:
        return override.strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}

    # Automatic Render Cloud detection
    if os.getenv("RENDER", "").lower() == "true" or bool(os.getenv("RENDER_SERVICE_ID")):
        return False

    return True


def get_vlm_model():
    """
    Lazy load and cache the SmolVLM model and LoRA adapter in memory.
    Ensures PyTorch / HuggingFace are NOT loaded on startup or during image upload.
    Only loaded when a user query explicitly invokes VLM analysis.
    """
    global _MODEL, _PROCESSOR

    if _MODEL is not None and _PROCESSOR is not None:
        return _MODEL, _PROCESSOR

    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText
    from peft import PeftModel

    print(f"Loading VLM processor from {ADAPTER_DIR if ADAPTER_DIR.exists() else MODEL_ID}...")
    if ADAPTER_DIR.exists():
        processor = AutoProcessor.from_pretrained(str(ADAPTER_DIR))
    else:
        processor = AutoProcessor.from_pretrained(MODEL_ID)

    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    print("Loading base SmolVLM model...")
    base_model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        dtype=torch_dtype,
        device_map="auto"
    )

    if ADAPTER_DIR.exists():
        print(f"Attaching fine-tuned Remote-Sensing LoRA adapter from {ADAPTER_DIR}...")
        model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))
    else:
        print("LoRA adapter directory not found, using base model.")
        model = base_model

    model.eval()

    _MODEL = model
    _PROCESSOR = processor
    return _MODEL, _PROCESSOR


def _norm_token(s: str) -> str:
    """Normalize any string to alphanumeric lowercase for robust fuzzy matching."""
    return re.sub(r"[^a-zA-Z0-9]", "", str(s)).lower()


def find_scene_image(upload_dir: Path = Path("uploads"), target_scene_id: str | None = None) -> Path | None:
    """
    Find a viewable PNG image for the VLM to analyze.
    Checks multispectral RGB composites first, then preview images,
    then direct uploads and benchmark images as fallback.
    """
    search_dirs = [upload_dir]
    try:
        if upload_dir.resolve() != Path("uploads").resolve():
            search_dirs.append(Path("uploads"))
    except Exception:
        pass

    # If target_scene_id is specified, strictly check for its specific images across search dirs
    if target_scene_id:
        t_clean = target_scene_id.strip()
        t_norm = _norm_token(t_clean)

        for base in search_dirs:
            if not base.exists():
                continue

            multispectral_dir = base / "multispectral"
            if multispectral_dir.exists():
                target_rgb = multispectral_dir / f"{t_clean}_RGB.png"
                if target_rgb.exists():
                    return target_rgb
                for rgb_match in multispectral_dir.glob("*_RGB.png"):
                    if t_clean in rgb_match.name or t_norm in _norm_token(rgb_match.stem):
                        return rgb_match

            preview_dir = base / "previews"
            if preview_dir.exists():
                for p in preview_dir.glob("*.png"):
                    if t_clean in p.name or t_norm in _norm_token(p.stem) or _norm_token(p.stem) in t_norm:
                        return p

            # Direct image uploads (PNG, JPG, JPEG)
            for img in base.iterdir():
                if img.is_file() and img.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                    img_norm = _norm_token(img.stem)
                    if (t_clean in img.name or
                        t_norm == img_norm or
                        t_norm in img_norm or
                        img_norm in t_norm):
                        return img

        # Target scene specified but no matching image found -> DO NOT fall through
        return None

    # Fallback when no target_scene_id is specified
    for base in search_dirs:
        if not base.exists():
            continue
        multispectral_dir = base / "multispectral"
        if multispectral_dir.exists():
            for rgb_img in multispectral_dir.glob("*_RGB.png"):
                return rgb_img
            for preview in multispectral_dir.glob("*.png"):
                return preview

        preview_dir = base / "previews"
        if preview_dir.exists():
            for preview in preview_dir.glob("*.png"):
                return preview

        for ext in [".png", ".jpg", ".jpeg"]:
            for img in base.glob(f"*{ext}"):
                if not img.name.endswith("_preview.png"):
                    return img

    # Check benchmark Sentinel-2 imagery
    benchmark_dir = Path("app/ai/dataset/rs_benchmark_images")
    if benchmark_dir.exists():
        for img in benchmark_dir.glob("*.png"):
            return img

    # Fallback to dataset image if available
    fallback_dir = Path("app/ai/dataset/images")
    if fallback_dir.exists():
        for img in fallback_dir.glob("*.png"):
            return img

    return None


def get_vlm_token_budget(query: str, default_max_tokens: int = 160) -> int:
    """
    Dynamically allocate token budget based on query intent:
    - Concise sentence requests: 64 tokens.
    - Factual / presence queries: 96 tokens.
    - Descriptive / open-ended queries: 160 tokens.
    """
    q = query.strip().lower()

    if "concise sentence" in q or "1 to 2" in q:
        return 64

    # Priority for descriptive requests even if phrased as a question
    descriptive_keywords = [
        "describe", "in detail", "detailed", "what features", "what major features",
        "what objects", "list all", "identify all", "explain the scene"
    ]
    if any(k in q for k in descriptive_keywords):
        return default_max_tokens

    # Check if query is explicitly asking for verification
    factual_starters = [
        "is there", "are there", "does this", "does it", "can you see",
        "do you see", "is it", "is that", "has this"
    ]
    if any(q.startswith(s) for s in factual_starters):
        return 96

    return default_max_tokens


def run_vlm_analysis(
    query: str = "Describe what you see in this satellite image.",
    image_path: Path | str | None = None,
    upload_dir: Path = Path("uploads"),
    output_dir: Path = Path("uploads/multispectral"),
    target_scene_id: str | None = None,
    target_scene: str | None = None,
    **kwargs
) -> dict:
    """
    Execute VLM inference using the fine-tuned LoRA model
    on a satellite scene image.
    """
    try:
        # Resolve target image
        resolved_image_path = None
        if image_path:
            p = Path(image_path)
            if p.exists():
                resolved_image_path = p

        if resolved_image_path is None:
            resolved_image_path = find_scene_image(
                upload_dir,
                target_scene_id=target_scene_id or target_scene
            )

        if resolved_image_path is None:
            tgt = target_scene_id or target_scene or "selected scene"
            return {
                "success": False,
                "tool": "remote_sensing_vlm",
                "error": f"The selected image file '{tgt}' could not be located on disk. Please verify the file exists or re-upload the image."
            }

        # Guard: Check deployment memory constraint before loading deep learning models
        if not is_local_vlm_enabled():
            ev_url = None
            if resolved_image_path:
                try:
                    rel_ev = resolved_image_path.resolve().relative_to(Path("uploads").resolve()).as_posix()
                    ev_url = f"/uploads/{rel_ev}"
                except Exception:
                    ev_url = f"/uploads/{resolved_image_path.name}"

            return {
                "success": True,
                "tool": "remote_sensing_vlm",
                "query": query,
                "scene_id": target_scene_id or target_scene,
                "image_analyzed": str(resolved_image_path) if resolved_image_path else None,
                "image_filename": resolved_image_path.name if resolved_image_path else None,
                "evidence": {
                    "scene_image": ev_url
                } if ev_url else {},
                "answer": (
                    "Vision-Language Model (VLM) deep inference is unavailable in this low-memory cloud deployment "
                    "(Render 512 MB RAM limit; SmolVLM-500M requires ~1.66 GB). "
                    "Deterministic scientific raster tools (NDVI Canopy, NDWI Water Delineation, 4-Band Spectral Signatures, "
                    "Bi-Temporal Change Differencing, and Optical + SAR Radar Fusion) remain fully active and functional."
                ),
                "vlm_available": False,
                "deployment_constrained": True,
                "model_metadata": {
                    "base_model": MODEL_ID,
                    "adapter_path": str(ADAPTER_DIR),
                    "status": "disabled_low_memory_deployment",
                    "required_ram_mb": 1700,
                    "available_host_limit_mb": 512
                }
            }

        # Load model and processor (cached in memory)
        model, processor = get_vlm_model()

        # Open and prepare image (strictly bound resolution to 384x384 to protect 4GB GTX 1650 VRAM)
        image = Image.open(resolved_image_path).convert("RGB")
        if image.width > 384 or image.height > 384:
            image.thumbnail((384, 384), Image.Resampling.BILINEAR)

        # Prepare chat conversation prompt
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": query}
                ]
            }
        ]

        prompt = processor.apply_chat_template(
            messages,
            add_generation_prompt=True
        )

        inputs = processor(
            text=prompt,
            images=[image],
            return_tensors="pt"
        )

        inputs = {
            key: value.to(model.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }

        # Determine query-aware token budget (concise for verification, 384 for descriptive)
        target_max_tokens = get_vlm_token_budget(query, default_max_tokens=384)

        # Natural stopping criteria: ensure eos_token_id and pad_token_id are set
        import torch
        eos_token_id = processor.tokenizer.eos_token_id
        pad_token_id = processor.tokenizer.pad_token_id or eos_token_id

        # Generate response with latency tracking and zero gradient allocation
        t0 = time.time()
        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=target_max_tokens,
                do_sample=False,
                pad_token_id=pad_token_id,
                eos_token_id=eos_token_id
            )
        latency = round(time.time() - t0, 2)

        answer = processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )[0]

        # Explicitly release GPU/RAM tensor references
        del inputs, generated_ids
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Clean answer if it repeats the prompt
        if "Assistant:" in answer:
            answer = answer.split("Assistant:")[-1].strip()

        # Stop duplicate section loops if generated (e.g. repeated analysis headings)
        if "### Analysis and Description" in answer:
            parts = answer.split("### Analysis and Description")
            if len(parts[0].strip()) > 100:
                answer = parts[0].strip()

        # Ensure answer stops naturally and doesn't end with an incomplete fragment
        last_punct = max(answer.rfind('.'), answer.rfind('!'), answer.rfind('?'))
        if last_punct > 120 and (len(answer) - last_punct) > 10 and not answer.endswith(('.', '!', '?', ':')):
            candidate = answer[:last_punct + 1].strip()
            if len(candidate) > 100:
                answer = candidate

        try:
            rel_ev = resolved_image_path.resolve().relative_to(Path("uploads").resolve()).as_posix()
            ev_url = f"/uploads/{rel_ev}"
        except Exception:
            ev_url = f"/uploads/{resolved_image_path.name}"
        return {
            "success": True,
            "tool": "remote_sensing_vlm",
            "query": query,
            "scene_id": target_scene_id or target_scene,
            "image_analyzed": str(resolved_image_path),
            "image_filename": resolved_image_path.name,
            "evidence": {
                "scene_image": ev_url
            },
            "answer": answer.strip(),
            "vlm_available": True,
            "deployment_constrained": False,
            "model_metadata": {
                "base_model": MODEL_ID,
                "adapter_path": str(ADAPTER_DIR),
                "adapter_active": ADAPTER_DIR.exists(),
                "max_new_tokens": target_max_tokens,
                "latency_seconds": latency,
                "device": str(model.device)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "remote_sensing_vlm",
            "error": str(e)
        }

