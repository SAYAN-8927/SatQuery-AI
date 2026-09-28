import json
from pathlib import Path
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText
from peft import PeftModel

MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
ADAPTER_DIR = "app/ai/lora_adapter_rs"
VAL_FILE = "app/ai/dataset/rs_vqa_val.jsonl"


def test_inference():
    print("=" * 60)
    print("PHASE 3 INFERENCE TEST: ADAPTED REMOTE-SENSING VLM")
    print("=" * 60)

    # 1. Read first held-out validation sample
    with open(VAL_FILE, "r", encoding="utf-8") as f:
        val_sample = json.loads(f.readline())

    image_path = val_sample["image"]
    ground_truth_class = val_sample["ground_truth_class"]
    user_query = val_sample["messages"][0]["content"][1]["text"]
    ground_truth_answer = val_sample["messages"][1]["content"][0]["text"]

    print(f"\n[1] Validation Image:       {image_path}")
    print(f"[2] Ground Truth Terrain:   {ground_truth_class}")
    print(f"[3] Test Query:             '{user_query}'")
    print(f"[4] Expected Reference:     '{ground_truth_answer}'")

    # 2. Load Processor and Model
    print(f"\n[5] Loading processor & fine-tuned adapter from {ADAPTER_DIR}...")
    processor = AutoProcessor.from_pretrained(ADAPTER_DIR)

    base_model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        dtype=torch.float16,
        device_map="auto"
    )

    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
    model.eval()

    # 3. Prepare Input
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

    # 4. Generate Answer
    print("\n[6] Generating answer from fine-tuned LoRA model...")
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=80)

    answer = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    if "Assistant:" in answer:
        answer = answer.split("Assistant:")[-1].strip()

    print("\n" + "=" * 60)
    print("MODEL OUTPUT")
    print("=" * 60)
    print(answer)
    print("=" * 60)


if __name__ == "__main__":
    test_inference()
