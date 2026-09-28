from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


UPLOAD_DIR = Path("uploads")

OUTPUT_DIR = Path(
    "app/ai/dataset/images"
)


SCENES = [
    "LC09_L2SP_141040_20260810_20260811_02_T1",
    "LC09_L2SP_141040_20260826_20260827_02_T1"
]


def read_band(scene_id: str, band: str):
    """
    Read a Landsat surface-reflectance band
    and convert digital numbers to reflectance.
    """

    path = (
        UPLOAD_DIR
        / f"{scene_id}_SR_{band}.TIF"
    )

    with rasterio.open(path) as dataset:
        data = dataset.read(1).astype(np.float32)

    # Landsat Collection 2 Level-2 scaling
    reflectance = (
        data * 0.0000275
        - 0.2
    )

    return reflectance


def percentile_stretch(array):
    """
    Convert reflectance values into
    an 8-bit display image.
    """

    valid = np.isfinite(array)

    if not np.any(valid):
        raise ValueError(
            "No valid pixels found."
        )

    low = np.percentile(
        array[valid],
        2
    )

    high = np.percentile(
        array[valid],
        98
    )

    if high <= low:
        high = low + 1e-6

    stretched = (
        (array - low)
        / (high - low)
    )

    stretched = np.clip(
        stretched,
        0,
        1
    )

    return (
        stretched * 255
    ).astype(np.uint8)


def create_rgb(scene_id: str):
    """
    Create a natural-color RGB image.

    Landsat:
        B4 = Red
        B3 = Green
        B2 = Blue
    """

    print(
        f"Processing RGB: {scene_id}"
    )

    red = read_band(
        scene_id,
        "B4"
    )

    green = read_band(
        scene_id,
        "B3"
    )

    blue = read_band(
        scene_id,
        "B2"
    )

    red = percentile_stretch(
        red
    )

    green = percentile_stretch(
        green
    )

    blue = percentile_stretch(
        blue
    )

    rgb = np.stack(
        [
            red,
            green,
            blue
        ],
        axis=-1
    )

    image = Image.fromarray(
        rgb,
        mode="RGB"
    )

    output_path = (
        OUTPUT_DIR
        / f"{scene_id}_RGB.png"
    )

    image.save(
        output_path
    )

    print(
        f"Saved: {output_path}"
    )

    return output_path


def create_nir_visualization(scene_id: str):
    """
    Create a grayscale visualization
    of Landsat Band 5 (NIR).
    """

    print(
        f"Processing NIR: {scene_id}"
    )

    nir = read_band(
        scene_id,
        "B5"
    )

    nir = percentile_stretch(
        nir
    )

    image = Image.fromarray(
        nir,
        mode="L"
    )

    output_path = (
        OUTPUT_DIR
        / f"{scene_id}_NIR.png"
    )

    image.save(
        output_path
    )

    print(
        f"Saved: {output_path}"
    )

    return output_path


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        "Preparing remote-sensing images..."
    )

    for scene_id in SCENES:

        create_rgb(
            scene_id
        )

        create_nir_visualization(
            scene_id
        )

    print(
        "\nImage preparation complete."
    )


if __name__ == "__main__":
    main()