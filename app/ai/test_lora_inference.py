from pathlib import Path
from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from peft import PeftModel

MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
ADAPTER_DIR = "app/ai/lora_test"

# Test image: Landsat RGB image from dataset
IMAGE_PATH = "app/ai/dataset/images/LC09_L2SP_141040_20260810_20260811_02_T1_RGB.png"

print("1. Loading processor from adapter...")
processor = AutoProcessor.from_pretrained(ADAPTER_DIR)

print("2. Loading base model...")
base_model = AutoModelForImageTextToText.from_pretrained(
    MODEL_ID,
    dtype=torch.float16,
    device_map="auto"
)

print("3. Attaching LoRA adapter...")
model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
model.eval()
print("Model with LoRA adapter loaded successfully!")

print(f"4. Loading image from {IMAGE_PATH}...")
image = Image.open(IMAGE_PATH).convert("RGB")

prompt_question = "What type of remote sensing image is this?"
print(f"User Query: '{prompt_question}'")

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image"},
            {"type": "text", "text": prompt_question}
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

print("5. Generating response...")
with torch.no_grad():
    generated_ids = model.generate(
        **inputs,
        max_new_tokens=80
    )

answer = processor.batch_decode(
    generated_ids,
    skip_special_tokens=True
)[0]

print("\n==============================")
print("FINE-TUNED LORA VLM ANSWER")
print("==============================")
print(answer)
