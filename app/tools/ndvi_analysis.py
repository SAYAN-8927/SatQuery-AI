from pathlib import Path

from app.services.multispectral_processor import (
    process_multispectral_scene
)


def run_ndvi_analysis(
    upload_dir: Path = Path("uploads"),
    output_dir: Path = Path("uploads/multispectral"),
    target_scene: str = None
):
    """
    Run NDVI analysis on a compatible Landsat scene.

    The existing multispectral processor:
    - finds B2, B3, B4 and B5
    - reads the satellite bands
    - applies Landsat surface-reflectance scaling
    - calculates NDVI
    - generates an NDVI preview
    """

    result = process_multispectral_scene(
        upload_dir=upload_dir,
        output_dir=output_dir,
        target_scene=target_scene
    )

    if not result["success"]:
        return {
            "success": False,
            "tool": "ndvi_analysis",
            "error": result["error"]
        }

    ndvi_preview_path = result["outputs"]["ndvi_preview"]
    ndvi_web_url = result["outputs"].get("ndvi_url") or f"/uploads/multispectral/{Path(ndvi_preview_path).name}"

    return {
        "success": True,
        "tool": "ndvi_analysis",
        "scene": result["scene"],

        "bands_used": {
            "red": "B4",
            "nir": "B5"
        },

        "ndvi_statistics": {
            **result["ndvi"],
            "mean_ndvi": result["ndvi"].get("mean")
        },

        "evidence": {
            "ndvi_map": ndvi_web_url,
            "ndvi_map_disk_path": str(ndvi_preview_path),
            "artifact_type": "ndvi_map",
            "filename": Path(ndvi_preview_path).name,
            "url": ndvi_web_url
        },

        "processing": {
            "crs": result["crs"],
            "original_dimensions": result["original_dimensions"],
            "processing_dimensions": result["processing_dimensions"]
        }
    }