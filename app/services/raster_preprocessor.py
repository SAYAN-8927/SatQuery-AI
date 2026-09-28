from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling


def create_preview(
    file_path: Path,
    output_dir: Path,
    size: int = 512
):
    """
    Create a small PNG preview from a raster image.

    The original GeoTIFF is not modified.
    """

    try:
        with rasterio.open(file_path) as dataset:

            # Read the first band at preview size using fast decimation resampling
            data = dataset.read(
                1,
                out_shape=(size, size),
                resampling=Resampling.nearest
            )

            # Convert to floating point for normalization
            data = data.astype(np.float32)

            # Remove NoData values from calculations (e.g. 0 background border pixels outside radar swath)
            if dataset.nodata is not None:
                valid_mask = (data != dataset.nodata)
            elif np.any(data > 0):
                valid_mask = (data > 0)
            else:
                valid_mask = np.ones_like(data, dtype=bool)

            valid_pixels = data[valid_mask]

            if valid_pixels.size == 0:
                valid_pixels = data.flatten()

            # Calculate useful display range
            minimum = float(np.percentile(valid_pixels, 2))
            maximum = float(np.percentile(valid_pixels, 98))

            # Prevent division by zero
            if maximum <= minimum:
                minimum = float(np.min(valid_pixels))
                maximum = float(np.max(valid_pixels))
                if maximum <= minimum:
                    maximum = minimum + 1.0

            # Normalize to 0-255
            norm = np.clip(data, minimum, maximum)
            norm = (
                (norm - minimum)
                / (maximum - minimum)
                * 255.0
            )

            # Preserve background border zeros as true black
            if not np.all(valid_mask):
                norm[~valid_mask] = 0.0

            data = norm.astype(np.uint8)

            # Save preview
            output_dir.mkdir(parents=True, exist_ok=True)

            output_path = (
                output_dir /
                f"{file_path.stem}_preview.png"
            )

            Image.fromarray(data).save(output_path)

            return {
                "success": True,
                "preview_path": str(output_path),
                "width": size,
                "height": size,
                "source_band": 1,
                "normalization": {
                    "minimum": float(minimum),
                    "maximum": float(maximum)
                }
            }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }