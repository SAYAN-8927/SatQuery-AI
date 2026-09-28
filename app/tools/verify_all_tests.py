import os
import json
import torch
from pathlib import Path
from app.tools.vlm_analysis import run_vlm_analysis

def verify_all():
    print("=" * 60)
    print("SATQUERY AI: VLM GENERATION TESTS A-E VERIFICATION")
    print("=" * 60)

    tests = [
        ("A", "Is there vegetation in this image?"),
        ("B", "Is there a road in this image?"),
        ("C", "Is there a water body in this image?"),
        ("D", "Describe this scene in detail."),
        ("E", "What major features are visible in this image?")
    ]

    img_path = Path("uploads/Screenshot (190).png")
    if not img_path.exists():
        print(f"Error: {img_path} not found")
        return

    results = []
    total_mem = round(torch.cuda.get_device_properties(0).total_memory / (1024**2), 1) if torch.cuda.is_available() else 0

    for letter, q in tests:
        print(f"\n--- Running Test {letter}: {q} ---")
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats(0)

        res = run_vlm_analysis(
            query=q,
            image_path=img_path,
            target_scene_id="Screenshot__190"
        )

        ans = res.get("answer", "")
        meta = res.get("model_metadata", {})
        peak_vram = round(torch.cuda.max_memory_allocated(0) / (1024**2), 1) if torch.cuda.is_available() else 0

        # Check if truncated mid-sentence
        ends_with_terminal_punct = ans.endswith((".", "!", "?", ":", '"'))

        entry = {
            "test": letter,
            "query": q,
            "max_new_tokens": meta.get("max_new_tokens"),
            "latency_seconds": meta.get("latency_seconds"),
            "peak_vram_mb": peak_vram,
            "total_vram_mb": total_mem,
            "response_length_chars": len(ans),
            "word_count": len(ans.split()),
            "ends_cleanly": ends_with_terminal_punct,
            "answer": ans
        }
        results.append(entry)

        print(f"Max New Tokens:   {entry['max_new_tokens']}")
        print(f"Response Length:  {entry['response_length_chars']} chars ({entry['word_count']} words)")
        print(f"Latency:          {entry['latency_seconds']}s")
        print(f"Peak VRAM:        {peak_vram} MB / {total_mem} MB")
        print(f"Ends Cleanly:     {ends_with_terminal_punct}")
        print(f"Answer:\n{ans}\n")

    os.makedirs("scratch", exist_ok=True)
    with open("scratch/vlm_test_verification.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("All tests completed and saved to scratch/vlm_test_verification.json")

if __name__ == "__main__":
    verify_all()
