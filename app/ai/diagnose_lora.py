import json
from pathlib import Path
import torch
from PIL import Image as PILImage
from peft import LoraConfig, get_peft_model
from transformers import AutoProcessor, AutoModelForImageTextToText

MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
DATASET_FILE = Path("app/ai/dataset/remote_sensing_train.jsonl")


def run_diagnosis():
    print("=" * 60)
    print("PHASE 1: LORA NUMERICAL STABILITY DIAGNOSTIC")
    print("=" * 60)

    # 1. Device and Environment Check
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[1] Device: {device}")
    if device == "cuda":
        torch.cuda.empty_cache()
        print(f"    GPU: {torch.cuda.get_device_name(0)}")
        print(f"    Total VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**2):.1f} MB")
        print(f"    Current Allocated: {torch.cuda.memory_allocated(0) / (1024**2):.1f} MB")

    # 2. Load 1 Training Example for exact diagnosis (Batch size = 1)
    print(f"\n[2] Reading 1 example from {DATASET_FILE}...")
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        example = json.loads(f.readline())

    raw_image_path = example["image"]
    raw_img = PILImage.open(raw_image_path)
    print(f"    Original image path: {raw_image_path}")
    print(f"    Original image dimensions: {raw_img.size} (Width x Height)")

    # 3. Controlled Image Resolution for 4GB VRAM
    # Sizing to 384x384 prevents tiling explosion in SmolVLM
    target_size = (384, 384)
    resized_img = raw_img.convert("RGB").resize(target_size, PILImage.Resampling.BILINEAR)
    print(f"    Controlled training resolution: {resized_img.size}")

    # 4. Load Processor & Special Tokens
    print(f"\n[3] Loading Processor for {MODEL_ID}...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    image_token_id = processor.tokenizer.convert_tokens_to_ids("<image>")
    fake_token_id = processor.tokenizer.convert_tokens_to_ids("<fake_token_around_image>")

    # 5. Collate Single Multimodal Item
    print("\n[4] Preparing multimodal batch (Batch Size = 1)...")
    text = processor.apply_chat_template(
        example["messages"],
        add_generation_prompt=False,
        tokenize=False
    )

    batch = processor(
        text=[text],
        images=[resized_img],
        padding=True,
        return_tensors="pt"
    )

    labels = batch["input_ids"].clone()
    total_tokens = labels.numel()
    image_tokens_masked = (labels == image_token_id).sum().item()
    fake_tokens_masked = (labels == fake_token_id).sum().item()

    labels[labels == image_token_id] = -100
    labels[labels == fake_token_id] = -100

    active_loss_tokens = (labels != -100).sum().item()

    print(f"    Total tokens in sequence: {total_tokens}")
    print(f"    Image tokens masked: {image_tokens_masked}")
    print(f"    Fake tokens masked: {fake_tokens_masked}")
    print(f"    Active tokens contributing to loss: {active_loss_tokens}")

    batch["labels"] = labels
    batch = {k: v.to(device) if hasattr(v, "to") else v for k, v in batch.items()}

    # 6. Load Base Model in FP16
    print(f"\n[5] Loading model {MODEL_ID} in float16...")
    base_model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map="auto"
    )

    # 7. Apply LoRA Config
    print("\n[6] Attaching LoRA adapter...")
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

    # Enable input gradients for proper backprop through frozen base model
    base_model.enable_input_require_grads()

    model = get_peft_model(base_model, lora_config)
    model.train()

    trainable_params = [p for p in model.parameters() if p.requires_grad]
    trainable_dtypes = set(p.dtype for p in trainable_params)
    print(f"    Trainable LoRA parameters: {sum(p.numel() for p in trainable_params):,}")
    print(f"    LoRA parameter dtypes: {trainable_dtypes}")

    if device == "cuda":
        print(f"    VRAM Allocated before forward: {torch.cuda.memory_allocated(0) / (1024**2):.1f} MB")

    # 8. Forward Pass
    print("\n[7] Running Forward Pass...")
    outputs = model(**batch)
    loss = outputs.loss
    loss_val = loss.item()
    print(f"    Forward Pass Loss: {loss_val:.4f}")
    print(f"    Is Loss finite? {torch.isfinite(loss).item()}")

    # 9. Backward Pass
    print("\n[8] Running Backward Pass...")
    loss.backward()

    nan_grads = 0
    inf_grads = 0
    finite_grads = 0
    grad_norms = []

    for name, p in model.named_parameters():
        if p.requires_grad and p.grad is not None:
            g = p.grad
            if torch.isnan(g).any():
                nan_grads += 1
                print(f"    [!] NaN gradient in: {name}")
            elif torch.isinf(g).any():
                inf_grads += 1
                print(f"    [!] Inf gradient in: {name}")
            else:
                finite_grads += 1
                grad_norms.append(g.norm(2).item())

    total_grad_norm = (sum(gn**2 for gn in grad_norms) ** 0.5) if grad_norms else 0.0

    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"Original Image Size:        {raw_img.size}")
    print(f"Training Resolution:        {target_size}")
    print(f"Tokens in Sequence:         {total_tokens}")
    print(f"Loss Value:                 {loss_val:.4f}")
    print(f"Loss is Finite:             {torch.isfinite(loss).item()}")
    print(f"Trainable layers checked:   {len(grad_norms) + nan_grads + inf_grads}")
    print(f"Finite gradient layers:     {finite_grads}")
    print(f"NaN gradient layers:        {nan_grads}")
    print(f"Inf gradient layers:        {inf_grads}")
    print(f"Total Computed Grad Norm:   {total_grad_norm:.4f}")
    if device == "cuda":
        print(f"Peak VRAM Used:             {torch.cuda.max_memory_allocated(0) / (1024**2):.1f} MB")
    print("=" * 60)

    if nan_grads == 0 and inf_grads == 0 and torch.isfinite(loss):
        print("RESULT: SUCCESS - Gradients and loss are completely finite!")
    else:
        print("RESULT: INSTABILITY DETECTED - Non-finite gradients or loss present.")


if __name__ == "__main__":
    run_diagnosis()
