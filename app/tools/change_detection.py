from pathlib import Path
import re
import shutil
import numpy as np
import rasterio
from rasterio.enums import Resampling
from PIL import Image, ImageDraw, ImageFont

from app.services.multispectral_processor import to_web_url


def parse_scene_date(scene_id: str) -> str:
    """
    Extract date from Landsat Collection 2 scene ID (e.g. LC09_..._20260810_... -> 2026-08-10).
    """
    match = re.search(r"_(\d{8})_\d{8}_", scene_id)
    if match:
        d = match.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return scene_id[:16]


def find_band_file(upload_dir: Path, scene_id: str, band: str):
    """
    Find a specific Landsat band for a specific scene.
    """
    search_dirs = [upload_dir]
    try:
        if Path("uploads").resolve() != upload_dir.resolve() and Path("uploads").exists():
            search_dirs.append(Path("uploads"))
    except Exception:
        pass

    possible_names = {
        f"{scene_id}_SR_{band}.TIF".upper(),
        f"{scene_id}_{band}.TIF".upper(),
        f"{scene_id}_SR_{band}.TIFF".upper(),
        f"{scene_id}_{band}.TIFF".upper()
    }
    for d in search_dirs:
        for f in d.iterdir():
            if f.is_file() and f.name.upper() in possible_names:
                return f
    return None


def read_reflectance(file_path: Path, size: int = 1024):
    """
    Read a Landsat Collection 2 Surface Reflectance band,
    resample safely to size x size, and scale DN to reflectance.
    """
    with rasterio.Env(GDAL_CACHEMAX=32), rasterio.open(file_path) as dataset:
        data = dataset.read(
            1,
            out_shape=(size, size),
            resampling=Resampling.bilinear
        ).astype(np.float32)
        profile = {
            "crs": str(dataset.crs),
            "nodata": dataset.nodata,
            "width": dataset.width,
            "height": dataset.height
        }
        nodata = dataset.nodata

    # Landsat Collection 2 Surface Reflectance scaling: DN * 0.0000275 - 0.2
    scaled = (data * 0.0000275) - 0.2

    if nodata is not None:
        scaled[data == nodata] = np.nan

    return scaled, profile


def calculate_ndvi(red, nir):
    """
    Calculate NDVI safely.
    NDVI = (NIR - Red) / (NIR + Red)
    """
    denominator = nir + red
    valid = np.isfinite(red) & np.isfinite(nir) & (np.abs(denominator) > 0.05)
    ndvi = np.full_like(red, np.nan, dtype=np.float32)
    ndvi[valid] = (nir[valid] - red[valid]) / denominator[valid]
    return np.clip(ndvi, -1.0, 1.0)


def get_or_create_scene_rgb(upload_dir: Path, scene_id: str, output_dir: Path, size: int = 512) -> Path:
    """
    Find or generate an RGB natural color composite for a scene.
    """
    # Check if multispectral RGB already exists
    multispectral_dir = upload_dir / "multispectral"
    if multispectral_dir.exists():
        existing = multispectral_dir / f"{scene_id}_RGB.png"
        if existing.exists():
            return existing

    out_path = output_dir / f"{scene_id}_RGB.png"
    if out_path.exists():
        return out_path

    # Build from B4 (Red), B3 (Green), B2 (Blue)
    f_red = find_band_file(upload_dir, scene_id, "B4")
    f_green = find_band_file(upload_dir, scene_id, "B3")
    f_blue = find_band_file(upload_dir, scene_id, "B2")

    if f_red and f_green and f_blue:
        r, _ = read_reflectance(f_red, size)
        g, _ = read_reflectance(f_green, size)
        b, _ = read_reflectance(f_blue, size)

        def norm_ch(ch):
            valid = np.isfinite(ch) & (ch > 0)
            if not np.any(valid):
                return np.zeros_like(ch, dtype=np.uint8)
            low = np.percentile(ch[valid], 2)
            high = np.percentile(ch[valid], 98)
            if high <= low:
                high = low + 0.1
            clipped = np.clip((ch - low) / (high - low), 0, 1)
            clipped = np.nan_to_num(clipped, nan=0.0)
            arr = (clipped * 255).astype(np.uint8)
            arr[~valid] = 0
            return arr

        rgb = np.dstack((norm_ch(r), norm_ch(g), norm_ch(b)))
        img = Image.fromarray(rgb)
        output_dir.mkdir(parents=True, exist_ok=True)
        img.save(out_path)
        return out_path

    # Fallback placeholder image if raw bands not accessible
    fallback_img = Image.new("RGB", (size, size), color="#1e293b")
    draw = ImageDraw.Draw(fallback_img)
    draw.text((size // 4, size // 2), f"Scene: {scene_id[:20]}", fill="#94a3b8")
    output_dir.mkdir(parents=True, exist_ok=True)
    fallback_img.save(out_path)
    return out_path


def create_colored_change_map(change_map: np.ndarray, output_path: Path):
    """
    Create a colored NDVI change map:
    - Green = Vegetation Gain (Δ > +0.10)
    - Red = Vegetation Loss / Deforestation (Δ < -0.10)
    - Slate Gray = Stable Surface (-0.10 <= Δ <= +0.10)
    - Dark Background = Invalid / Nodata
    """
    h, w = change_map.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    # Dark background for nodata
    rgb[:] = [15, 23, 42]

    valid = np.isfinite(change_map)

    # Stable (Neutral Slate Gray)
    stable_mask = valid & (change_map >= -0.10) & (change_map <= 0.10)
    rgb[stable_mask] = [100, 116, 139]

    # Vegetation Gain (Vibrant Green)
    gain_mask = valid & (change_map > 0.10)
    rgb[gain_mask] = [34, 197, 94]

    # Vegetation Loss / Degradation (Vibrant Red)
    loss_mask = valid & (change_map < -0.10)
    rgb[loss_mask] = [239, 68, 68]

    img = Image.fromarray(rgb)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path


def create_side_by_side_triplet(
    before_rgb_path: Path,
    after_rgb_path: Path,
    change_map_path: Path,
    before_date: str,
    after_date: str,
    stats: dict,
    output_path: Path
) -> Path:
    """
    Generate a 3-panel visual evidence composite:
    [ BEFORE SCENE ] | [ AFTER SCENE ] | [ NDVI CHANGE MAP ]
    Includes clear panel banners, date tags, and a statistical legend.
    """
    panel_w = 380
    panel_h = 360
    header_h = 50
    footer_h = 50
    total_w = panel_w * 3 + 40
    total_h = header_h + panel_h + footer_h

    canvas = Image.new("RGB", (total_w, total_h), color="#0f172a")
    draw = ImageDraw.Draw(canvas)

    # Header Banner
    draw.rectangle([(0, 0), (total_w, header_h)], fill="#1e293b")
    draw.text(
        (25, 15),
        f"SatQuery AI — Bi-Temporal Change Detection: {before_date} vs {after_date}",
        fill="#38bdf8"
    )

    # Load and resize 3 images
    def load_panel(p):
        try:
            im = Image.open(p).convert("RGB")
            return im.resize((panel_w, panel_h), Image.Resampling.BILINEAR)
        except Exception:
            im = Image.new("RGB", (panel_w, panel_h), color="#1e293b")
            return im

    p1 = load_panel(before_rgb_path)
    p2 = load_panel(after_rgb_path)
    p3 = load_panel(change_map_path)

    # Paste panels
    x1 = 10
    x2 = x1 + panel_w + 10
    x3 = x2 + panel_w + 10
    y = header_h + 5

    canvas.paste(p1, (x1, y))
    canvas.paste(p2, (x2, y))
    canvas.paste(p3, (x3, y))

    # Panel border & labels
    for x, label, color in [
        (x1, f"1. BEFORE ({before_date})", "#38bdf8"),
        (x2, f"2. AFTER ({after_date})", "#a855f7"),
        (x3, "3. NDVI CHANGE MAP", "#22c55e")
    ]:
        draw.rectangle([(x, y), (x + panel_w, y + panel_h)], outline="#334155", width=2)
        # Semi-transparent tag at top of panel
        draw.rectangle([(x + 5, y + 5), (x + 220, y + 28)], fill="#0f172a")
        draw.text((x + 12, y + 9), label, fill=color)

    # Footer Legend Banner
    draw.rectangle([(0, total_h - footer_h), (total_w, total_h)], fill="#1e293b")
    inc_pct = stats.get("vegetation_gain_percentage") if stats.get("vegetation_gain_percentage") is not None else stats.get("increase_percentage", 0.0)
    dec_pct = stats.get("vegetation_loss_percentage") if stats.get("vegetation_loss_percentage") is not None else stats.get("decrease_percentage", 0.0)
    stb_pct = stats.get("stable_percentage", 0.0)
    m_chg = stats.get("mean_delta_ndvi") if stats.get("mean_delta_ndvi") is not None else stats.get("mean_ndvi_change", 0.0)

    # Legend chips
    draw.rectangle([(25, total_h - 32), (37, total_h - 20)], fill="#22c55e")
    draw.text((45, total_h - 33), f"Vegetation Gain: {inc_pct:.1f}%", fill="#f8fafc")

    draw.rectangle([(250, total_h - 32), (262, total_h - 20)], fill="#ef4444")
    draw.text((270, total_h - 33), f"Vegetation Loss: {dec_pct:.1f}%", fill="#f8fafc")

    draw.rectangle([(475, total_h - 32), (487, total_h - 20)], fill="#64748b")
    draw.text((495, total_h - 33), f"Stable Terrain: {stb_pct:.1f}%", fill="#f8fafc")

    draw.text((720, total_h - 33), f"Net ΔNDVI: {m_chg:+.3f}", fill="#38bdf8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def run_change_detection(
    upload_dir: Path = Path("uploads"),
    output_dir: Path = Path("uploads/change_detection"),
    before_scene_id: str | None = None,
    after_scene_id: str | None = None,
    size: int = 1024,
    **kwargs
):
    """
    Perform bi-temporal NDVI change detection and generate
    both a colored change map and a 3-panel comparison triplet.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if before_scene_id is None or after_scene_id is None:
        return {
            "success": False,
            "tool": "change_detection",
            "error": "Before and after scene IDs are required."
        }

    before_date = parse_scene_date(before_scene_id)
    after_date = parse_scene_date(after_scene_id)

    # 1. Locate B4 (Red) and B5 (NIR)
    before_b4 = find_band_file(upload_dir, before_scene_id, "B4")
    before_b5 = find_band_file(upload_dir, before_scene_id, "B5")
    after_b4 = find_band_file(upload_dir, after_scene_id, "B4")
    after_b5 = find_band_file(upload_dir, after_scene_id, "B5")

    missing = []
    if not before_b4: missing.append("before B4")
    if not before_b5: missing.append("before B5")
    if not after_b4: missing.append("after B4")
    if not after_b5: missing.append("after B5")

    if missing:
        return {
            "success": False,
            "tool": "change_detection",
            "error": f"Required bands missing: {', '.join(missing)}"
        }

    # 2. Read and scale reflectance
    before_red, before_profile = read_reflectance(before_b4, size)
    before_nir, _ = read_reflectance(before_b5, size)
    after_red, after_profile = read_reflectance(after_b4, size)
    after_nir, _ = read_reflectance(after_b5, size)

    # 3. Calculate NDVI
    ndvi_before = calculate_ndvi(before_red, before_nir)
    ndvi_after = calculate_ndvi(after_red, after_nir)

    # 4. Calculate NDVI Difference: After - Before
    ndvi_change = ndvi_after - ndvi_before
    valid = np.isfinite(ndvi_change) & np.isfinite(ndvi_before) & np.isfinite(ndvi_after)

    if not np.any(valid):
        return {
            "success": False,
            "tool": "change_detection",
            "error": "No valid pixels produced for NDVI change difference."
        }

    valid_before = ndvi_before[valid]
    valid_after = ndvi_after[valid]
    valid_change = ndvi_change[valid]

    before_mean = float(np.mean(valid_before))
    after_mean = float(np.mean(valid_after))
    mean_change = float(np.mean(valid_change))
    std_change = float(np.std(valid_change))
    min_change = float(np.min(valid_change))
    max_change = float(np.max(valid_change))

    # 5. Classify spatial change dynamics
    increase_threshold = 0.10
    decrease_threshold = -0.10

    increase_pixels = int(np.sum(valid_change > increase_threshold))
    decrease_pixels = int(np.sum(valid_change < decrease_threshold))
    stable_pixels = int(np.sum((valid_change >= decrease_threshold) & (valid_change <= increase_threshold)))
    total_valid = len(valid_change)

    inc_pct = round(float((increase_pixels / total_valid) * 100.0), 2)
    dec_pct = round(float((decrease_pixels / total_valid) * 100.0), 2)
    stb_pct = round(100.0 - inc_pct - dec_pct, 2)

    # Spatial hotspot / dynamic classification
    if inc_pct > dec_pct + 5.0:
        dynamic_classification = "Net Vegetation Greening / Seasonal Growth Dominant"
    elif dec_pct > inc_pct + 5.0:
        dynamic_classification = "Net Vegetation Loss / Canopy Degradation Dominant"
    else:
        dynamic_classification = "Balanced Seasonal Dynamic / Stable Ecosystem"

    stats = {
        # Authoritative Single Source of Truth
        "baseline_mean_ndvi": round(before_mean, 4),
        "monitoring_mean_ndvi": round(after_mean, 4),
        "mean_delta_ndvi": round(mean_change, 4),
        "vegetation_gain_percentage": inc_pct,
        "vegetation_loss_percentage": dec_pct,
        "stable_percentage": stb_pct,

        # Standard Aliases for Full Backward Compatibility
        "before_mean_ndvi": round(before_mean, 4),
        "after_mean_ndvi": round(after_mean, 4),
        "delta_mean_ndvi": round(mean_change, 4),
        "mean_ndvi_change": round(mean_change, 4),
        "increase_percentage": inc_pct,
        "decrease_percentage": dec_pct,

        "stddev": round(std_change, 4),
        "min": round(min_change, 4),
        "max": round(max_change, 4),
        "total_analyzed_pixels": total_valid,
        "dynamic_classification": dynamic_classification
    }

    # 6. Generate Colored Change Map
    change_map_filename = f"{before_scene_id}_to_{after_scene_id}_NDVI_change.png"
    change_map_path = output_dir / change_map_filename
    create_colored_change_map(ndvi_change, change_map_path)

    # 7. Get / Create Before and After RGB Composites
    before_rgb = get_or_create_scene_rgb(upload_dir, before_scene_id, output_dir, size=512)
    after_rgb = get_or_create_scene_rgb(upload_dir, after_scene_id, output_dir, size=512)

    # 8. Generate 3-Panel Side-by-Side Comparison Triplet
    triplet_filename = f"{before_scene_id}_to_{after_scene_id}_comparison_triplet.png"
    triplet_path = output_dir / triplet_filename
    create_side_by_side_triplet(
        before_rgb_path=before_rgb,
        after_rgb_path=after_rgb,
        change_map_path=change_map_path,
        before_date=before_date,
        after_date=after_date,
        stats=stats,
        output_path=triplet_path
    )

    # Mirror artifacts to uploads/change_detection/ to guarantee web accessibility
    mirror_dir = Path("uploads") / "change_detection"
    mirror_dir.mkdir(parents=True, exist_ok=True)
    try:
        for src, fname in [
            (change_map_path, change_map_filename),
            (triplet_path, triplet_filename),
            (before_rgb, before_rgb.name),
            (after_rgb, after_rgb.name)
        ]:
            dst = mirror_dir / fname
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
    except Exception:
        pass

    change_map_url = to_web_url(change_map_path)
    triplet_url = to_web_url(triplet_path)

    return {
        "success": True,
        "tool": "change_detection_model",
        "method": "Bi-temporal NDVI Differencing",
        "before": {
            "scene_id": before_scene_id,
            "date": before_date,
            "b4": before_b4.name,
            "b5": before_b5.name,
            "rgb_preview": str(before_rgb)
        },
        "after": {
            "scene_id": after_scene_id,
            "date": after_date,
            "b4": after_b4.name,
            "b5": after_b5.name,
            "rgb_preview": str(after_rgb)
        },
        "statistics": stats,
        "evidence": {
            "change_map": change_map_url,
            "comparison_triplet": triplet_url,
            "triplet_disk_path": str(triplet_path),
            "before_rgb": to_web_url(before_rgb),
            "after_rgb": to_web_url(after_rgb),
            "artifact_type": "comparison_triplet",
            "filename": triplet_filename,
            "url": triplet_url
        },
        "processing_metadata": {
            "crs": before_profile.get("crs"),
            "resolution": f"{size}x{size}"
        }
    }


if __name__ == "__main__":
    res = run_change_detection(
        before_scene_id="LC09_L2SP_141040_20260810_20260811_02_T1",
        after_scene_id="LC09_L2SP_141040_20260826_20260827_02_T1"
    )
    print("Change detection result:", res.get("success"))
    print("Stats:", res.get("statistics"))
    print("Evidence:", res.get("evidence"))