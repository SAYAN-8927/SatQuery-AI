import json
from pathlib import Path


OUTPUT_FILE = Path(
    "app/ai/dataset/remote_sensing_train.jsonl"
)

IMAGE_DIR = Path(
    "app/ai/dataset/images"
)


examples = []


# --------------------------------------------------
# RGB examples
# --------------------------------------------------

rgb_questions = [
    (
        "What type of remote sensing image is this?",
        "This is an RGB visualization created from Landsat multispectral bands. It represents a remote sensing observation rather than a normal camera photograph."
    ),
    (
        "Which Landsat bands were used to create this RGB image?",
        "The RGB visualization was created using Landsat surface reflectance bands B4, B3, and B2, corresponding to Red, Green, and Blue."
    ),
    (
        "Why is this RGB visualization useful for remote sensing?",
        "It provides a visually interpretable representation of the multispectral satellite data and helps users understand land cover and surface features."
    ),
    (
        "Is this a normal camera photograph?",
        "No. This is a visualization generated from multispectral Landsat satellite data."
    ),
]


# --------------------------------------------------
# NIR examples
# --------------------------------------------------

nir_questions = [
    (
        "What spectral information does this image represent?",
        "This image represents Near Infrared spectral information from the Landsat B5 band."
    ),
    (
        "Why is Near Infrared useful for vegetation analysis?",
        "Healthy vegetation strongly reflects Near Infrared radiation, making the NIR band useful for identifying and analyzing vegetation."
    ),
    (
        "Which other band is required with Near Infrared to calculate NDVI?",
        "The Red band, Landsat B4, is required together with the Near Infrared band, Landsat B5, to calculate NDVI."
    ),
    (
        "Is this a normal grayscale photograph?",
        "No. It is a visualization of Near Infrared satellite data."
    ),
]


# --------------------------------------------------
# Find generated images
# --------------------------------------------------

for image_path in sorted(IMAGE_DIR.glob("*.png")):

    filename = image_path.name

    if "_RGB.png" in filename:
        image_type = "RGB"
        questions = rgb_questions

    elif "_NIR.png" in filename:
        image_type = "NIR"
        questions = nir_questions

    else:
        continue

    # Extract scene ID
    scene_id = filename.rsplit("_", 1)[0]

    # Extract date from Landsat scene ID
    parts = scene_id.split("_")

    date = "unknown"

    if len(parts) >= 4:
        raw_date = parts[3]

        if len(raw_date) == 8:
            date = (
                f"{raw_date[:4]}-"
                f"{raw_date[4:6]}-"
                f"{raw_date[6:]}"
            )

    for question, answer in questions:

        example = {
            "image": str(image_path),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image"
                        },
                        {
                            "type": "text",
                            "text": question
                        }
                    ]
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": answer
                        }
                    ]
                }
            ],
            "scene_id": scene_id,
            "date": date,
            "image_type": image_type
        }

        examples.append(example)


# --------------------------------------------------
# Write JSONL
# --------------------------------------------------

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    for example in examples:
        f.write(
            json.dumps(
                example,
                ensure_ascii=False
            )
            + "\n"
        )


print(
    f"Created {len(examples)} training examples."
)

print(
    f"Saved to: {OUTPUT_FILE}"
)