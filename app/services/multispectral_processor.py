from pathlib import Path
import re
import shutil

import numpy as np
import rasterio
from rasterio.enums import Resampling
from PIL import Image


def to_web_url(disk_path: Path | str) -> str:
    """
    Convert a filesystem path under uploads/ to a URL-safe web path served by FastAPI.
    Guarantees forward slashes and preserves the workspace subpath.
    """
    if not disk_path:
        return ""
    try:
        p = Path(disk_path).resolve()
        uploads_root = Path("uploads").resolve()
        rel = p.relative_to(uploads_root).as_posix()
        return f"/uploads/{rel}"
    except (ValueError, Exception):
        clean = str(disk_path).replace("\\", "/").strip()
        if not clean.startswith("/"):
            clean = "/" + clean
        return clean


def render_calibrated_ndvi_map(ndvi: np.ndarray, valid_mask: np.ndarray, output_path: Path) -> Path:
    """
    Render a calibrated false-color NDVI spatial map (RGB PNG).
    Color scale matches scientific remote sensing standards:
      - Masked/Invalid: Dark Slate [15, 23, 42]
      - NDVI < 0.0: Water Bodies / Non-vegetation (Deep Blue [30, 64, 175] to Earth Brown [146, 64, 14])
      - 0.0 <= NDVI < 0.2: Sparse / Mixed Vegetation & Soil (Warm Sand / Amber [234, 179, 8])
      - 0.2 <= NDVI < 0.5: Moderate Canopy (Lively Lime Green [132, 204, 22])
      - NDVI >= 0.5: Dense Forest Canopy (Deep Emerald Green [21, 128, 61])
    """
    h, w = ndvi.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:] = [15, 23, 42]  # Dark background for nodata

    valid = valid_mask & np.isfinite(ndvi)
    if not np.any(valid):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgb).save(output_path)
        return output_path

    # Water / Non-vegetation: [-1.0, 0.0)
    water_mask = valid & (ndvi < 0.0)
    if np.any(water_mask):
        w_norm = np.clip((ndvi[water_mask] + 1.0), 0.0, 1.0)
        r = (30 + w_norm * (146 - 30)).astype(np.uint8)
        g = (64 + w_norm * (64 - 64)).astype(np.uint8)
        b = (175 + w_norm * (14 - 175)).astype(np.uint8)
        rgb[water_mask] = np.column_stack((r, g, b))

    # Sparse / Mixed Vegetation: [0.0, 0.2)
    sparse_mask = valid & (ndvi >= 0.0) & (ndvi < 0.2)
    if np.any(sparse_mask):
        s_norm = np.clip(ndvi[sparse_mask] / 0.2, 0.0, 1.0)
        r = (217 + s_norm * (234 - 217)).astype(np.uint8)
        g = (119 + s_norm * (179 - 119)).astype(np.uint8)
        b = (6 + s_norm * (8 - 6)).astype(np.uint8)
        rgb[sparse_mask] = np.column_stack((r, g, b))

    # Moderate Canopy: [0.2, 0.5)
    mod_mask = valid & (ndvi >= 0.2) & (ndvi < 0.5)
    if np.any(mod_mask):
        m_norm = np.clip((ndvi[mod_mask] - 0.2) / 0.3, 0.0, 1.0)
        r = (234 + m_norm * (132 - 234)).astype(np.uint8)
        g = (179 + m_norm * (204 - 179)).astype(np.uint8)
        b = (8 + m_norm * (22 - 8)).astype(np.uint8)
        rgb[mod_mask] = np.column_stack((r, g, b))

    # Dense Canopy: [0.5, 1.0]
    dense_mask = valid & (ndvi >= 0.5)
    if np.any(dense_mask):
        d_norm = np.clip((ndvi[dense_mask] - 0.5) / 0.5, 0.0, 1.0)
        r = (132 + d_norm * (21 - 132)).astype(np.uint8)
        g = (204 + d_norm * (128 - 204)).astype(np.uint8)
        b = (22 + d_norm * (61 - 22)).astype(np.uint8)
        rgb[dense_mask] = np.column_stack((r, g, b))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(output_path)
    return output_path


REQUIRED_BANDS = {
    "B2": "Blue",
    "B3": "Green",
    "B4": "Red",
    "B5": "NIR"
}


def find_landsat_bands(upload_dir: Path, target_scene: str = None):
    pattern = re.compile(
        r"^(?P<scene>.+?)(?:_SR)?_(?P<band>B(?:[1-9]|1[0-1]))\.TIFF?$",
        re.IGNORECASE
    )

    if isinstance(upload_dir, (list, tuple)):
        dirs = [Path(d) for d in upload_dir if Path(d).exists()]
    else:
        dirs = [Path(upload_dir)] if Path(upload_dir).exists() else []

    try:
        uploads_resolved = Path("uploads").resolve()
        if not any(d.resolve() == uploads_resolved for d in dirs) and Path("uploads").exists():
            dirs.append(Path("uploads"))
    except Exception:
        pass

    scenes = {}

    for d in dirs:
        for file_path in d.iterdir():
            if not file_path.is_file():
                continue
            match = pattern.match(file_path.name)
            if not match:
                continue

            scene = match.group("scene").upper()
            band = match.group("band").upper()

            scenes.setdefault(scene, {})[band] = file_path

    # If a specific target scene is requested, strictly search for it without falling back
    if target_scene:
        t_clean = target_scene.upper().strip()
        for scene, bands in scenes.items():
            if t_clean in scene or scene in t_clean:
                # NDVI requires B4 (Red) and B5 (NIR); B2 and B3 provide supplemental RGB
                if "B4" in bands and "B5" in bands:
                    return {
                        "found": True,
                        "scene": scene,
                        "bands": bands
                    }
                else:
                    missing = [b for b in ["B4", "B5"] if b not in bands]
                    return {
                        "found": False,
                        "reason": f"Target scene '{target_scene}' is missing required bands: {', '.join(missing)}."
                    }
        return {
            "found": False,
            "reason": f"Target scene '{target_scene}' was not found in uploads catalog."
        }

    for scene, bands in scenes.items():
        if "B4" in bands and "B5" in bands:
            return {
                "found": True,
                "scene": scene,
                "bands": bands
            }

    return {
        "found": False,
        "reason": (
            "Could not find required B4 (Red) and B5 (NIR) bands "
            "from the requested Landsat scene."
        )
    }


def read_band(file_path: Path, size: int = 1024):

    with rasterio.open(file_path) as dataset:

        data = dataset.read(
            1,
            out_shape=(size, size),
            resampling=Resampling.bilinear
        )

        profile = {
            "width": dataset.width,
            "height": dataset.height,
            "crs": str(dataset.crs),
            "nodata": dataset.nodata
        }

    return data.astype(np.float32), profile


def scale_landsat_surface_reflectance(
    data,
    nodata=None
):
    """
    Convert raw Landsat Collection 2 Level-2 DN values to surface reflectance.
    Standard USGS formula: SR = (DN * 0.0000275) - 0.2
    Enforces non-negative physical surface reflectance constraint (SR >= 0.0).
    """
    data = data.astype(np.float32)

    if nodata is not None:
        invalid = data == nodata
    elif np.any(data == 0) and np.any(data > 0):
        # Standard USGS Landsat Level-1/2 DN fill value is 0
        invalid = data == 0
    else:
        invalid = np.zeros(
            data.shape,
            dtype=bool
        )

    scaled = (
        data * 0.0000275
    ) - 0.2

    scaled[invalid] = np.nan
    # Clamp valid physical surface reflectance to [0.0, 1.0]
    scaled = np.where(np.isnan(scaled), np.nan, np.clip(scaled, 0.0, 1.0))

    return scaled


def normalize_channel(
    data,
    valid_mask,
    low=1,
    high=99
):

    valid = data[valid_mask]

    if valid.size == 0:
        raise ValueError(
            "RGB channel contains no valid pixels."
        )

    minimum = np.percentile(
        valid,
        low
    )

    maximum = np.percentile(
        valid,
        high
    )

    if maximum <= minimum:
        return np.zeros(
            data.shape,
            dtype=np.uint8
        )

    result = np.clip(
        data,
        minimum,
        maximum
    )

    result = (
        (result - minimum)
        / (maximum - minimum)
        * 255
    )

    result = np.nan_to_num(
        result,
        nan=0
    )

    return result.astype(np.uint8)


def calculate_ndvi(nir, red):
    """
    Calculate Normalized Difference Vegetation Index (NDVI):
        NDVI = (NIR - Red) / (NIR + Red)
    Guards against:
        - Negative reflectance values
        - Near-zero / zero denominators
        - Out-of-bound values: strictly clips to [-1.0, +1.0]
    """
    denominator = nir + red
    valid_mask = (
        np.isfinite(nir)
        & np.isfinite(red)
        & (nir >= 0.0)
        & (red >= 0.0)
        & (denominator > 1e-6)
    )

    ndvi = np.full_like(nir, np.nan, dtype=np.float32)
    ndvi[valid_mask] = (nir[valid_mask] - red[valid_mask]) / denominator[valid_mask]

    # Strict physical boundary clipping to [-1.0, 1.0]
    return np.clip(ndvi, -1.0, 1.0)


def process_multispectral_scene(
    upload_dir: Path,
    output_dir: Path,
    size: int = 1024,
    target_scene: str = None
):

    scene_result = find_landsat_bands(
        upload_dir,
        target_scene=target_scene
    )

    if not scene_result["found"]:
        return {
            "success": False,
            "error": scene_result["reason"]
        }

    scene = scene_result["scene"]
    bands = scene_result["bands"]

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        # -----------------------------------------
        # Read the satellite bands (B4 & B5 mandatory, B2 & B3 optional)
        # -----------------------------------------
        b4, p4 = read_band(
            bands["B4"],
            size
        )

        b5, p5 = read_band(
            bands["B5"],
            size
        )

        has_rgb = "B2" in bands and "B3" in bands
        if has_rgb:
            b2, p2 = read_band(
                bands["B2"],
                size
            )
            b3, p3 = read_band(
                bands["B3"],
                size
            )

            crs_values = {
                p2["crs"],
                p3["crs"],
                p4["crs"],
                p5["crs"]
            }

            if len(crs_values) != 1:
                return {
                    "success": False,
                    "error": (
                        "The satellite bands do not have "
                        "matching CRS information."
                    )
                }

            b2 = scale_landsat_surface_reflectance(
                b2,
                p2["nodata"]
            )
            b3 = scale_landsat_surface_reflectance(
                b3,
                p3["nodata"]
            )
        else:
            if p4["crs"] != p5["crs"]:
                return {
                    "success": False,
                    "error": (
                        "B4 and B5 do not have "
                        "matching CRS information."
                    )
                }

        # -----------------------------------------
        # Convert Landsat DN to reflectance
        # -----------------------------------------
        b4 = scale_landsat_surface_reflectance(
            b4,
            p4["nodata"]
        )

        b5 = scale_landsat_surface_reflectance(
            b5,
            p5["nodata"]
        )

        # -----------------------------------------
        # Common valid pixel mask
        # -----------------------------------------
        valid_mask = (
            np.isfinite(b4)
            & np.isfinite(b5)
            & (b4 >= 0)
            & (b5 >= 0)
        )

        if has_rgb:
            valid_mask = (
                valid_mask
                & np.isfinite(b2)
                & np.isfinite(b3)
                & (b2 >= 0)
                & (b3 >= 0)
            )

        if not np.any(valid_mask):
            return {
                "success": False,
                "error": (
                    "No valid pixels were found "
                    "in the satellite bands."
                )
            }

        # -----------------------------------------
        # Natural color RGB or false-color preview
        # -----------------------------------------
        rgb_path = (
            output_dir
            / f"{scene}_RGB.png"
        )

        if has_rgb:
            red = normalize_channel(
                b4,
                valid_mask
            )
            green = normalize_channel(
                b3,
                valid_mask
            )
            blue = normalize_channel(
                b2,
                valid_mask
            )
            rgb = np.dstack(
                (
                    red,
                    green,
                    blue
                )
            )
            rgb[~valid_mask] = 0
            Image.fromarray(
                rgb
            ).save(rgb_path)
        else:
            # Generate false-color representation with B5, B4, B4
            red = normalize_channel(
                b5,
                valid_mask
            )
            green = normalize_channel(
                b4,
                valid_mask
            )
            blue = normalize_channel(
                b4,
                valid_mask
            )
            rgb = np.dstack(
                (
                    red,
                    green,
                    blue
                )
            )
            rgb[~valid_mask] = 0
            Image.fromarray(
                rgb
            ).save(rgb_path)

        # -----------------------------------------
        # NIR preview
        # -----------------------------------------
        nir_display = normalize_channel(
            b5,
            valid_mask
        )
        nir_display[~valid_mask] = 0

        nir_path = (
            output_dir
            / f"{scene}_NIR.png"
        )

        Image.fromarray(
            nir_display
        ).save(nir_path)

        # -----------------------------------------
        # NDVI calculation (scientific calculation unchanged)
        # -----------------------------------------
        ndvi = calculate_ndvi(
            b5,
            b4
        )

        ndvi_mask = (
            np.isfinite(ndvi)
            & valid_mask
        )

        valid_ndvi = ndvi[
            ndvi_mask
        ]

        if valid_ndvi.size == 0:
            return {
                "success": False,
                "error": "Could not calculate NDVI."
            }

        ndvi_min = float(
            np.percentile(
                valid_ndvi,
                2
            )
        )

        ndvi_max = float(
            np.percentile(
                valid_ndvi,
                98
            )
        )

        if ndvi_max <= ndvi_min:
            return {
                "success": False,
                "error": (
                    "NDVI does not contain "
                    "enough variation."
                )
            }

        ndvi_path = (
            output_dir
            / f"{scene}_NDVI.png"
        )

        # Generate scientific false-color calibrated NDVI spatial map
        render_calibrated_ndvi_map(
            ndvi,
            ndvi_mask,
            ndvi_path
        )

        # Mirror generated artifacts to uploads/multispectral/ to guarantee
        # access regardless of whether URL includes workspaces/{id}/ or not
        mirror_dir = Path("uploads") / "multispectral"
        mirror_dir.mkdir(parents=True, exist_ok=True)
        try:
            target_ndvi = mirror_dir / f"{scene}_NDVI.png"
            if ndvi_path.resolve() != target_ndvi.resolve():
                shutil.copy2(ndvi_path, target_ndvi)
            if rgb_path.exists():
                target_rgb = mirror_dir / f"{scene}_RGB.png"
                if rgb_path.resolve() != target_rgb.resolve():
                    shutil.copy2(rgb_path, target_rgb)
            if nir_path.exists():
                target_nir = mirror_dir / f"{scene}_NIR.png"
                if nir_path.resolve() != target_nir.resolve():
                    shutil.copy2(nir_path, target_nir)
        except Exception:
            pass

        # URL-safe web paths with forward slashes
        ndvi_url = to_web_url(ndvi_path)
        rgb_url = to_web_url(rgb_path) if rgb_path.exists() else None
        nir_url = to_web_url(nir_path) if nir_path.exists() else None

        bands_used = {
            "B4": "Red (0.64 - 0.67 µm)",
            "B5": "Near Infrared (0.85 - 0.88 µm)"
        }
        if has_rgb:
            bands_used["B2"] = "Blue (0.45 - 0.51 µm)"
            bands_used["B3"] = "Green (0.53 - 0.59 µm)"

        # -----------------------------------------
        # Final result
        # -----------------------------------------
        return {

            "success": True,

            "scene": scene,

            "bands_used": bands_used,

            "crs": p4["crs"],

            "original_dimensions": {
                "width": p4["width"],
                "height": p4["height"]
            },

            "processing_dimensions": {
                "width": size,
                "height": size
            },

            "outputs": {
                "rgb_preview": str(
                    rgb_path
                ),
                "nir_preview": str(
                    nir_path
                ),
                "ndvi_preview": str(
                    ndvi_path
                ),
                "ndvi_url": ndvi_url,
                "rgb_url": rgb_url,
                "nir_url": nir_url,
            },

            "ndvi": {
                "mean": float(
                    np.mean(valid_ndvi)
                ),
                "stddev": float(
                    np.std(valid_ndvi)
                ),
                "display_min": ndvi_min,
                "display_max": ndvi_max
            }
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }