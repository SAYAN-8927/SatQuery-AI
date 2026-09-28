import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText
from peft import PeftModel

MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
ADAPTER_DIR = "app/ai/lora_adapter_rs"
VAL_FILE = "app/ai/dataset/rs_vqa_val.jsonl"
OUTPUT_DIR = Path("app/ai/dataset")
PREDICTIONS_FILE = OUTPUT_DIR / "evaluation_predictions.jsonl"
METRICS_FILE = OUTPUT_DIR / "evaluation_metrics.json"

# Associated domain keywords for the 10 European Space Agency classes
CLASS_KEYWORDS = {
    "Annual Crop": ["crop", "cropland", "agricultural", "farm", "field", "cultivated"],
    "Forest": ["forest", "woodland", "trees", "canopy", "timber"],
    "Herbaceous Vegetation": ["herbaceous", "grassland", "shrub", "grass", "meadow", "vegetation"],
    "Highway": ["highway", "road", "transportation", "paved", "infrastructure"],
    "Industrial Buildings": ["industrial", "commercial", "building", "warehouse", "facility", "structure"],
    "Pasture": ["pasture", "grazing", "grassland", "meadow", "grass"],
    "Permanent Crop": ["permanent crop", "orchard", "vineyard", "plantation", "perennial", "crop"],
    "Residential Buildings": ["residential", "housing", "houses", "urban", "settlement", "neighborhood", "building"],
    "River": ["river", "waterway", "water", "channel", "stream"],
    "SeaLake": ["water", "lake", "sea", "ocean", "surface water"]
}


def run_evaluation(num_samples: int = 30):
    print("=" * 65)
    print("PHASE 4: VLM BENCHMARK EVALUATION (Held-Out Test Data)")
    print("=" * 65)

    # 1. Load Validation Data
    print(f"\n[1] Reading held-out validation samples from {VAL_FILE}...")
    all_val_samples = []
    with open(VAL_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_val_samples.append(json.loads(line))

    print(f"    Total unseen test samples in dataset: {len(all_val_samples)}")

    # Sample a balanced subset across all 10 classes
    samples_by_class = {}
    for sample in all_val_samples:
        c = sample["ground_truth_class"]
        samples_by_class.setdefault(c, []).append(sample)

    eval_samples = []
    samples_per_class = max(1, num_samples // len(samples_by_class))
    for c, items in samples_by_class.items():
        eval_samples.extend(items[:samples_per_class])

    print(f"    Selected {len(eval_samples)} balanced test samples across all 10 terrain classes.")

    # 2. Load Adapted Model
    print(f"\n[2] Loading SmolVLM with fine-tuned Remote-Sensing Adapter from {ADAPTER_DIR}...")
    processor = AutoProcessor.from_pretrained(ADAPTER_DIR)

    base_model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        dtype=torch.float16,
        device_map="auto"
    )

    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
    model.eval()
    print("    Model loaded in evaluation mode.")

    # 3. Run Benchmark Inference
    print(f"\n[3] Running inference and scoring on {len(eval_samples)} unseen test questions...\n")

    predictions = []
    terrain_correct = 0
    verification_correct = 0
    verification_total = 0
    total_latency = 0.0

    for i, sample in enumerate(eval_samples, 1):
        image_path = sample["image"]
        ground_truth_class = sample["ground_truth_class"]
        user_query = sample["messages"][0]["content"][1]["text"]
        ground_truth_answer = sample["messages"][1]["content"][0]["text"]

        image = Image.open(image_path).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": user_query}
                ]
            }
        ]

        prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(text=prompt, images=[image], return_tensors="pt")
        inputs = {k: v.to(model.device) if hasattr(v, "to") else v for k, v in inputs.items()}

        t0 = time.time()
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=60)
        dt = time.time() - t0
        total_latency += dt

        raw_pred = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        if "Assistant:" in raw_pred:
            predicted_answer = raw_pred.split("Assistant:")[-1].strip()
        else:
            predicted_answer = raw_pred.strip()

        # Score Terrain Classification match
        pred_lower = predicted_answer.lower()
        expected_keywords = CLASS_KEYWORDS.get(ground_truth_class, [ground_truth_class.lower()])
        is_terrain_match = any(kw in pred_lower for kw in expected_keywords)
        if is_terrain_match:
            terrain_correct += 1

        # Score Binary Verification (Yes/No questions)
        is_verification = False
        is_verif_match = False
        gt_lower = ground_truth_answer.lower()
        if gt_lower.startswith("yes") or gt_lower.startswith("no"):
            is_verification = True
            verification_total += 1
            gt_is_yes = gt_lower.startswith("yes")
            pred_is_yes = "yes" in pred_lower[:15]
            pred_is_no = "no" in pred_lower[:15] or "not detected" in pred_lower or "not visible" in pred_lower

            if (gt_is_yes and pred_is_yes) or (not gt_is_yes and pred_is_no):
                verification_correct += 1
                is_verif_match = True

        predictions.append({
            "sample_index": i,
            "patch_id": sample.get("patch_id", f"patch_{i}"),
            "image_path": image_path,
            "ground_truth_class": ground_truth_class,
            "query": user_query,
            "ground_truth_answer": ground_truth_answer,
            "predicted_answer": predicted_answer,
            "terrain_keyword_match": is_terrain_match,
            "is_verification_question": is_verification,
            "verification_correct": is_verif_match if is_verification else None,
            "latency_seconds": round(dt, 3)
        })

        status_flag = "[MATCH]" if (is_terrain_match or is_verif_match) else "[-]"
        print(f"[{i:02d}/{len(eval_samples):02d}] Class: {ground_truth_class:22s} | Latency: {dt:.2f}s | {status_flag}")

    # 4. Compute Metrics
    terrain_accuracy = (terrain_correct / len(eval_samples)) * 100.0
    verif_accuracy = (verification_correct / verification_total * 100.0) if verification_total > 0 else 0.0
    avg_latency = total_latency / len(eval_samples)

    # 5. Save Results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(PREDICTIONS_FILE, "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    summary_metrics = {
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_test_samples": len(eval_samples),
        "terrain_classes_evaluated": len(samples_by_class),
        "terrain_accuracy_percentage": round(terrain_accuracy, 2),
        "verification_accuracy_percentage": round(verif_accuracy, 2),
        "overall_recognition_accuracy": round((terrain_correct + verification_correct) / (len(eval_samples) + verification_total) * 100.0, 2),
        "average_inference_latency_seconds": round(avg_latency, 3),
        "tested_model": MODEL_ID,
        "adapter_tested": ADAPTER_DIR
    }

    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(summary_metrics, f, indent=2)

    # 6. Report Scorecard
    print("\n" + "=" * 65)
    print("PHASE 4 BENCHMARK EVALUATION SCORECARD")
    print("=" * 65)
    print(f"Total Unseen Samples Evaluated:      {len(eval_samples)}")
    print(f"Terrain Classes Covered:             {len(samples_by_class)} (All ESA classes)")
    print(f"Terrain Classification Accuracy:     {terrain_accuracy:.2f}%")
    print(f"Verification Question Accuracy:      {verif_accuracy:.2f}%")
    print(f"Overall Recognition Accuracy:        {summary_metrics['overall_recognition_accuracy']:.2f}%")
    print(f"Average Inference Latency:           {avg_latency:.2f}s / question")
    print("-" * 65)
    print(f"[+] Prediction logs saved to:        {PREDICTIONS_FILE}")
    print(f"[+] Scorecard saved to:              {METRICS_FILE}")
    print("=" * 65)
    print("PHASE 4 EVALUATION COMPLETE!")


if __name__ == "__main__":
    run_evaluation(num_samples=30)
