import json
import random
from pathlib import Path
from PIL import Image
from datasets import load_dataset

OUTPUT_DIR = Path("app/ai/dataset")
IMAGES_DIR = OUTPUT_DIR / "rs_benchmark_images"

# 10 Official Sentinel-2 Land Cover Classes
CLASS_DESCRIPTIONS = {
    "Annual Crop": {
        "land_cover": "agricultural cropland with annual crops",
        "has_vegetation": True,
        "has_water": False,
        "has_urban": False,
        "detail": "regular cultivated agricultural fields used for annual crop farming"
    },
    "Forest": {
        "land_cover": "dense forest canopy and woodland",
        "has_vegetation": True,
        "has_water": False,
        "has_urban": False,
        "detail": "dense tree canopy with high biomass and strong vegetation signal"
    },
    "Herbaceous Vegetation": {
        "land_cover": "natural herbaceous vegetation and shrubland",
        "has_vegetation": True,
        "has_water": False,
        "has_urban": False,
        "detail": "open natural grassland and wild herbaceous plants"
    },
    "Highway": {
        "land_cover": "transportation corridor and highway infrastructure",
        "has_vegetation": False,
        "has_water": False,
        "has_urban": True,
        "detail": "paved roads, highway corridors, and surrounding infrastructure"
    },
    "Industrial Buildings": {
        "land_cover": "industrial facilities and commercial structures",
        "has_vegetation": False,
        "has_water": False,
        "has_urban": True,
        "detail": "large industrial complexes, commercial warehouses, and artificial impermeable surfaces"
    },
    "Pasture": {
        "land_cover": "managed pasture and agricultural grassland",
        "has_vegetation": True,
        "has_water": False,
        "has_urban": False,
        "detail": "managed grazing land and open grassy meadows"
    },
    "Permanent Crop": {
        "land_cover": "permanent agricultural plantations (orchards or vineyards)",
        "has_vegetation": True,
        "has_water": False,
        "has_urban": False,
        "detail": "structured perennial crop fields such as fruit orchards and vineyards"
    },
    "Residential Buildings": {
        "land_cover": "residential housing and urban settlements",
        "has_vegetation": False,
        "has_water": False,
        "has_urban": True,
        "detail": "residential neighborhoods with housing units and local road networks"
    },
    "River": {
        "land_cover": "river waterway and riparian corridor",
        "has_vegetation": False,
        "has_water": True,
        "has_urban": False,
        "detail": "a flowing inland river channel with distinct water surface reflectance"
    },
    "SeaLake": {
        "land_cover": "open surface water body (lake or sea)",
        "has_vegetation": False,
        "has_water": True,
        "has_urban": False,
        "detail": "an expansive open surface water body exhibiting low optical reflectance"
    }
}


def generate_vqa_pairs(image_path_str: str, class_name: str, patch_id: str):
    info = CLASS_DESCRIPTIONS[class_name]
    pairs = []

    # 1. Land Cover Question
    q1_variants = [
        "What type of land cover is visible in this satellite observation?",
        "What terrain or surface feature is observed here?",
        "Classify the land use shown in this remote sensing image."
    ]
    a1 = f"This satellite observation shows {info['land_cover']}. The surface is characterized by {info['detail']}."
    pairs.append((random.choice(q1_variants), a1))

    # 2. Vegetation Verification
    q2_variants = [
        "Is there vegetation present in this scene?",
        "Does this remote sensing image contain vegetation cover?"
    ]
    if info["has_vegetation"]:
        a2 = f"Yes, vegetation is clearly present. The scene features {info['land_cover']}."
    else:
        a2 = f"No significant vegetation cover is observed in this scene. The observation is dominated by {info['land_cover']}."
    pairs.append((random.choice(q2_variants), a2))

    # 3. Water Verification
    q3_variants = [
        "Are water bodies or surface water visible in this observation?",
        "Is water detected in this satellite patch?"
    ]
    if info["has_water"]:
        a3 = f"Yes, open surface water is prominently visible, showing {info['land_cover']}."
    else:
        a3 = f"No, surface water is not detected in this scene."
    pairs.append((random.choice(q3_variants), a3))

    # 4. Urban / Structural Question
    if info["has_urban"]:
        q4 = "Are man-made urban structures visible in this image?"
        a4 = f"Yes, man-made structures are observed, specifically {info['land_cover']}."
        pairs.append((q4, a4))

    # 5. Comprehensive Remote Sensing Description
    q5_variants = [
        "Describe what you see in this satellite image.",
        "Provide a remote-sensing scene description for this patch."
    ]
    a5 = (
        f"A multi-spectral satellite observation depicting {info['land_cover']}. "
        f"Surface features include {info['detail']}. "
        f"{'Vegetation signals are prominent' if info['has_vegetation'] else 'The area is primarily non-vegetated'}."
    )
    pairs.append((random.choice(q5_variants), a5))

    formatted_examples = []
    for q, a in pairs:
        formatted_examples.append({
            "image": image_path_str,
            "patch_id": patch_id,
            "ground_truth_class": class_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": q}
                    ]
                },
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": a}
                    ]
                }
            ]
        })

    return formatted_examples


def build_pipeline(num_samples_per_class: int = 15):
    print("=" * 60)
    print("PHASE 2: REAL REMOTE-SENSING DATASET PIPELINE")
    print("=" * 60)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(42)

    print("\n[1] Streaming Sentinel-2 / EuroSAT satellite benchmark dataset...")
    ds = load_dataset("blanchon/EuroSAT_RGB", split="train", streaming=True)
    class_names = ds.features["label"].names

    # Collect balanced samples per class
    collected_per_class = {c: 0 for c in class_names}
    all_vqa_examples = []
    total_needed = num_samples_per_class * len(class_names)

    print(f"    Targeting {num_samples_per_class} patches per class ({total_needed} total patches)...")

    for item in ds:
        label_idx = item["label"]
        class_name = class_names[label_idx]

        if collected_per_class[class_name] >= num_samples_per_class:
            if all(v >= num_samples_per_class for v in collected_per_class.values()):
                break
            continue

        patch_idx = collected_per_class[class_name]
        safe_class = class_name.replace(" ", "_").lower()
        patch_id = f"s2_{safe_class}_{patch_idx:03d}"
        image_filename = f"{patch_id}.png"
        image_path = IMAGES_DIR / image_filename

        # Save image scaled cleanly to 384x384
        img: Image.Image = item["image"].convert("RGB")
        img_resized = img.resize((384, 384), Image.Resampling.BILINEAR)
        img_resized.save(image_path)

        # Generate VQA pairs
        vqa_pairs = generate_vqa_pairs(str(image_path), class_name, patch_id)
        all_vqa_examples.extend(vqa_pairs)

        collected_per_class[class_name] += 1
        print(f"    [+] Saved patch {patch_id} ({class_name}) - Generated {len(vqa_pairs)} VQA pairs")

    print("\n[2] Creating Train / Validation Split (80% Train, 20% Val)...")
    # Group by patch to prevent image leakage between train and val
    patch_ids = list(set(ex["patch_id"] for ex in all_vqa_examples))
    random.shuffle(patch_ids)

    val_split_count = int(len(patch_ids) * 0.20)
    val_patch_ids = set(patch_ids[:val_split_count])
    train_patch_ids = set(patch_ids[val_split_count:])

    train_examples = [ex for ex in all_vqa_examples if ex["patch_id"] in train_patch_ids]
    val_examples = [ex for ex in all_vqa_examples if ex["patch_id"] in val_patch_ids]

    train_file = OUTPUT_DIR / "rs_vqa_train.jsonl"
    val_file = OUTPUT_DIR / "rs_vqa_val.jsonl"

    with open(train_file, "w", encoding="utf-8") as f:
        for ex in train_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    with open(val_file, "w", encoding="utf-8") as f:
        for ex in val_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print("\n" + "=" * 60)
    print("PHASE 2 DATASET PIPELINE SUMMARY")
    print("=" * 60)
    print(f"Total Satellite Patches:     {len(patch_ids)}")
    print(f"Total VQA QA Pairs:          {len(all_vqa_examples)}")
    print(f"Train Patches:               {len(train_patch_ids)} ({len(train_examples)} QA pairs)")
    print(f"Val Patches:                 {len(val_patch_ids)} ({len(val_examples)} QA pairs)")
    print(f"Train File:                  {train_file}")
    print(f"Val File:                    {val_file}")
    print(f"Image Directory:             {IMAGES_DIR}")
    print("=" * 60)
    print("PHASE 2 DATASET GENERATION COMPLETE!")


if __name__ == "__main__":
    build_pipeline(num_samples_per_class=15)
