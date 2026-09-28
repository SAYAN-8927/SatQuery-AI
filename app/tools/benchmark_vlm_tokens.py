import time
import torch
from pathlib import Path
from PIL import Image
from app.tools.vlm_analysis import get_vlm_model

def run_benchmark():
    print("=" * 60)
    print("SATQUERY AI: VLM GENERATION TOKEN BENCHMARK ON GTX 1650 4GB")
    print("=" * 60)

    if not torch.cuda.is_available():
        print("CUDA is NOT available! Cannot run GPU benchmark.")
        return

    device_name = torch.cuda.get_device_name(0)
    total_mem = round(torch.cuda.get_device_properties(0).total_memory / (1024**2), 1)
    print(f"Device: {device_name} | Total VRAM: {total_mem} MB")

    img_path = Path("uploads/Screenshot (190).png")
    if not img_path.exists():
        print(f"Test image {img_path} not found!")
        return

    model, processor = get_vlm_model()

    image = Image.open(img_path).convert("RGB")
    if image.width > 384 or image.height > 384:
        image.thumbnail((384, 384), Image.Resampling.BILINEAR)

    query = "Describe this scene in detail."
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": query}
            ]
        }
    ]

    prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(text=prompt, images=[image], return_tensors="pt")
    inputs = {k: v.to(model.device) if hasattr(v, "to") else v for k, v in inputs.items()}

    token_candidates = [256, 384, 512]

    for max_tokens in token_candidates:
        print("\n" + "-" * 50)
        print(f"TESTING max_new_tokens = {max_tokens}")
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(0)

        t0 = time.time()
        with torch.no_grad():
            gen_out = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=False,
                pad_token_id=processor.tokenizer.pad_token_id or processor.tokenizer.eos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id
            )
        latency = round(time.time() - t0, 2)

        peak_allocated = round(torch.cuda.max_memory_allocated(0) / (1024**2), 1)
        peak_reserved = round(torch.cuda.max_memory_reserved(0) / (1024**2), 1)

        # Count tokens generated
        input_len = inputs["input_ids"].shape[1]
        num_generated = gen_out.shape[1] - input_len

        decoded = processor.batch_decode(gen_out, skip_special_tokens=True)[0]
        if "Assistant:" in decoded:
            clean_answer = decoded.split("Assistant:")[-1].strip()
        else:
            clean_answer = decoded.strip()

        hit_limit = (num_generated >= max_tokens)
        stopped_naturally = not hit_limit

        print(f"Generated Tokens:     {num_generated} / {max_tokens}")
        print(f"Latency:              {latency}s ({round(num_generated / max(latency, 0.01), 1)} tokens/sec)")
        print(f"Peak VRAM Allocated:  {peak_allocated} MB / {total_mem} MB ({round(peak_allocated/total_mem*100, 1)}%)")
        print(f"Peak VRAM Reserved:   {peak_reserved} MB / {total_mem} MB ({round(peak_reserved/total_mem*100, 1)}%)")
        print(f"Natural Stop (EOS):   {stopped_naturally}")
        print(f"Text Character Count: {len(clean_answer)}")
        print(f"Ending Sample:        ...{clean_answer[-60:]!r}")
        print(f"Full Answer:\n{clean_answer}")

if __name__ == "__main__":
    run_benchmark()
