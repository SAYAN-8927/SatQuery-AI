from pathlib import Path

import torch
from PIL import Image as PILImage

from datasets import load_dataset
from peft import LoraConfig
from transformers import (
    AutoProcessor,
    AutoModelForImageTextToText,
    TrainingArguments,
)
from trl import SFTTrainer


MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"

DATASET_FILE = (
    "app/ai/dataset/remote_sensing_train.jsonl"
)

OUTPUT_DIR = "app/ai/lora_test"


# =========================================================
# Load dataset
# =========================================================

print("Loading dataset...")

dataset = load_dataset(
    "json",
    data_files=DATASET_FILE,
    split="train"
)

dataset = dataset.select(
    range(min(2, len(dataset)))
)

print(
    f"Training examples: {len(dataset)}"
)


# =========================================================
# Load processor
# =========================================================

print("Loading processor...")

processor = AutoProcessor.from_pretrained(
    MODEL_ID
)

image_token_id = processor.tokenizer.convert_tokens_to_ids("<image>")
fake_token_id = processor.tokenizer.convert_tokens_to_ids("<fake_token_around_image>")


# =========================================================
# Load model
# =========================================================

print("Loading model...")

model = AutoModelForImageTextToText.from_pretrained(
    MODEL_ID,
    dtype=torch.float16,
    device_map="auto"
)

print("Model loaded.")
model.enable_input_require_grads()


# =========================================================
# Custom multimodal collator
# =========================================================

def multimodal_collator(examples):

    images = []
    texts = []

    for example in examples:

        image_path = example["image"]

        image = PILImage.open(
            image_path
        ).convert("RGB").resize((384, 384), PILImage.Resampling.BILINEAR)

        images.append(image)

        messages = example["messages"]

        # Build the conversation using the model's
        # chat template.
        text = processor.apply_chat_template(
            messages,
            add_generation_prompt=False,
            tokenize=False
        )

        texts.append(text)

    batch = processor(
        text=texts,
        images=images,
        padding=True,
        return_tensors="pt"
    )

    labels = batch["input_ids"].clone()

    # Mask image tokens so loss is NOT computed on image placeholders
    labels[labels == image_token_id] = -100
    labels[labels == fake_token_id] = -100

    # Ignore padding in loss
    if "attention_mask" in batch:
        labels[
            batch["attention_mask"] == 0
        ] = -100

    batch["labels"] = labels

    return batch


# =========================================================
# LoRA configuration
# =========================================================

# Target language model attention layers to avoid unstable vision gradients
target_modules = [
    f"model.text_model.layers.{i}.self_attn.{proj}"
    for i in range(32)
    for proj in ["q_proj", "k_proj", "v_proj", "o_proj"]
]

lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    target_modules=target_modules,
    bias="none",
    task_type="CAUSAL_LM"
)


# =========================================================
# Training configuration
# =========================================================

training_args = TrainingArguments(

    output_dir=OUTPUT_DIR,

    per_device_train_batch_size=1,

    gradient_accumulation_steps=1,

    max_steps=5,

    learning_rate=5e-5,

    max_grad_norm=1.0,

    warmup_steps=1,

    fp16=False,

    gradient_checkpointing=True,

    logging_steps=1,

    save_strategy="no",

    report_to="none",

    remove_unused_columns=False
)


# =========================================================
# Trainer
# =========================================================

trainer = SFTTrainer(

    model=model,

    args=training_args,

    train_dataset=dataset,

    data_collator=multimodal_collator,

    peft_config=lora_config
)


# =========================================================
# Start training
# =========================================================

print()
print("Starting LoRA multi-step test...")
print()


trainer.train()


print()
print("===================================")
print("LoRA multi-step test completed!")
print("===================================")
print()
print("Saving fine-tuned adapter...")
trainer.save_model(OUTPUT_DIR)
processor.save_pretrained(OUTPUT_DIR)
print(f"Adapter saved successfully to {OUTPUT_DIR}")