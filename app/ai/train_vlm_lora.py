import json
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
TRAIN_FILE = "app/ai/dataset/rs_vqa_train.jsonl"
VAL_FILE = "app/ai/dataset/rs_vqa_val.jsonl"
OUTPUT_DIR = "app/ai/lora_adapter_rs"


def main():
    print("=" * 65)
    print("PHASE 3: REMOTE-SENSING VLM ADAPTATION (LoRA on GTX 1650 4GB)")
    print("=" * 65)

    # 1. Load Datasets
    print(f"\n[1] Loading real remote-sensing VQA datasets...")
    train_dataset = load_dataset("json", data_files=TRAIN_FILE, split="train")
    val_dataset = load_dataset("json", data_files=VAL_FILE, split="train")

    print(f"    Train examples available: {len(train_dataset)}")
    print(f"    Val examples available:   {len(val_dataset)}")

    # 2. Load Processor
    print(f"\n[2] Loading SmolVLM Processor...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    image_token_id = processor.tokenizer.convert_tokens_to_ids("<image>")
    fake_token_id = processor.tokenizer.convert_tokens_to_ids("<fake_token_around_image>")

    # 3. Multimodal Collator with Controlled Resolution
    def multimodal_collator(examples):
        images = []
        texts = []

        for example in examples:
            img = PILImage.open(example["image"]).convert("RGB")
            # Enforce 384x384 resolution to prevent token explosion & OOM on 4GB VRAM
            img = img.resize((384, 384), PILImage.Resampling.BILINEAR)
            images.append(img)

            text = processor.apply_chat_template(
                example["messages"],
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
        labels[labels == image_token_id] = -100
        labels[labels == fake_token_id] = -100

        if "attention_mask" in batch:
            labels[batch["attention_mask"] == 0] = -100

        batch["labels"] = labels
        return batch

    # 4. Load Base Model in FP16
    print(f"\n[3] Loading base model {MODEL_ID} in float16...")
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        dtype=torch.float16,
        device_map="auto"
    )

    # Enable input gradients for gradient checkpointing stability with LoRA
    model.enable_input_require_grads()
    print("    Model loaded successfully onto device:", next(model.parameters()).device)

    # 5. LoRA Configuration
    print(f"\n[4] Configuring LoRA adapters...")
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

    # 6. Training Configuration (Phase 1 Verified Stable Settings)
    print(f"\n[5] Setting up TrainingArguments (4GB VRAM Optimized)...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,  # Effective batch size = 4
        max_steps=30,                   # Focused, high-efficiency adaptation
        learning_rate=5e-5,
        warmup_steps=3,
        max_grad_norm=1.0,              # Gradient clipping prevents spikes
        fp16=False,                     # LoRA weights updated directly in FP32 (bypasses NaN scaler)
        gradient_checkpointing=True,    # Conserves activation VRAM
        logging_steps=5,
        save_strategy="no",
        report_to="none",
        remove_unused_columns=False
    )

    # 7. SFT Trainer
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=multimodal_collator,
        peft_config=lora_config
    )

    # 8. Run Adaptation
    print("\n" + "=" * 65)
    print("STARTING REMOTE-SENSING VLM ADAPTATION TRAINING")
    print("=" * 65 + "\n")

    train_result = trainer.train()

    print("\n" + "=" * 65)
    print("TRAINING FINISHED! SAVING REMOTE-SENSING ADAPTER")
    print("=" * 65)

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    trainer.save_model(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)

    # Save metrics log
    metrics_path = Path(OUTPUT_DIR) / "training_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(train_result.metrics, f, indent=2)

    print(f"\n[+] Fine-tuned Remote Sensing LoRA Adapter saved to: {OUTPUT_DIR}")
    print(f"[+] Training metrics log saved to: {metrics_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
