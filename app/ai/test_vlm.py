from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import torch


MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"

IMAGE_PATH = (
    "uploads/previews/"
    "LC08_L2SP_009012_20260720_20260725_02_T1_SR_B4_preview.png"
)


print("Loading processor...")

processor = AutoProcessor.from_pretrained(
    MODEL_ID
)

print("Loading model...")

model = AutoModelForImageTextToText.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    device_map="auto"
)

print("Model loaded successfully!")

print(
    "Model device:",
    next(model.parameters()).device
)


# --------------------------------------------------
# Load image
# --------------------------------------------------

print("Loading image...")

image = Image.open(
    IMAGE_PATH
).convert("RGB")


# --------------------------------------------------
# Create VLM conversation
# --------------------------------------------------

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image"
            },
            {
                "type": "text",
                "text": "Describe what you see in this image."
            }
        ]
    }
]


prompt = processor.apply_chat_template(
    messages,
    add_generation_prompt=True
)


# --------------------------------------------------
# Prepare inputs
# --------------------------------------------------

inputs = processor(
    text=prompt,
    images=[image],
    return_tensors="pt"
)

inputs = {
    key: value.to(model.device)
    if hasattr(value, "to")
    else value
    for key, value in inputs.items()
}


# --------------------------------------------------
# Generate answer
# --------------------------------------------------

print("Generating answer...")

generated_ids = model.generate(
    **inputs,
    max_new_tokens=100
)


answer = processor.batch_decode(
    generated_ids,
    skip_special_tokens=True
)[0]


print("\n==============================")
print("VLM ANSWER")
print("==============================")
print(answer)