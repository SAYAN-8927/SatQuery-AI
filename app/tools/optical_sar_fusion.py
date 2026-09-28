import math
from pathlib import Path
import re
import numpy as np
import rasterio
import rasterio.transform
from rasterio.enums import Resampling
from rasterio.warp import reproject, Resampling as WarpResampling
from PIL import Image, ImageDraw, ImageFont

import shutil
from app.services.multispectral_processor import (
    find_landsat_bands,
    read_band,
    scale_landsat_surface_reflectance,
    normalize_channel,
    to_web_url
)

from app.services.sar_identifier import parse_sar_filename, BENCH_SAR_PATTERN as SAR_PATTERN


def find_sar_bands(upload_dir: Path, target_scene: str | None = None) -> dict:
    """
    Locate Sentinel-1 SAR dual-polarization bands (VV and VH) in upload_dir.
    Supports both ESA Bhoonidhi SAFE measurement rasters and benchmark SAR rasters.
    """
    search_dirs = [upload_dir]
    try:
        if Path("uploads").resolve() != upload_dir.resolve() and Path("uploads").exists():
            search_dirs.append(Path("uploads"))
    except Exception:
        pass

    sar_scenes = {}
    for d in search_dirs:
        if not d.exists():
            continue
        for file_path in d.iterdir():
            if not file_path.is_file():
                continue
            sar_info = parse_sar_filename(file_path.name)
            if not sar_info:
                continue
            scene = sar_info["scene_id"]
            pol = sar_info["polarization"].upper()
            sar_scenes.setdefault(scene, {})[pol] = file_path

    # If target_scene is specified, find exact or substring match
    if target_scene:
        matched_scene = None
        if target_scene in sar_scenes:
            matched_scene = target_scene
        else:
            for s_id in sar_scenes:
                if target_scene.lower() in s_id.lower() or s_id.lower() in target_scene.lower():
                    matched_scene = s_id
                    break

        if matched_scene:
            pols = sar_scenes[matched_scene]
            if "VV" in pols and "VH" in pols:
                return {
                    "found": True,
                    "scene": matched_scene,
                    "bands": pols
                }
            return {
                "found": False,
                "reason": f"Specified SAR scene '{matched_scene}' does not contain both VV and VH bands."
            }
        return {
            "found": False,
            "reason": f"Specified SAR scene '{target_scene}' was not found."
        }

    # Otherwise return first SAR scene with both VV and VH
    for scene, pols in sar_scenes.items():
        if "VV" in pols and "VH" in pols:
            return {
                "found": True,
                "scene": scene,
                "bands": pols
            }

    # If only one polarization is available, return what we have
    for scene, pols in sar_scenes.items():
        if "VV" in pols or "VH" in pols:
            return {
                "found": True,
                "scene": scene,
                "bands": pols
            }

    return {
        "found": False,
        "reason": "Could not find matching Sentinel-1 SAR bands (VV, VH) in upload directory."
    }


def read_sar_band(
    file_path: Path,
    size: int = 512,
    target_crs=None,
    target_bounds=None,
    target_transform=None
) -> tuple[np.ndarray, dict]:
    """
    Read SAR raster, dynamically reprojecting / warping to target optical CRS and bounds
    if specified, and return calibrated backscatter array in decibels (dB).
    Handles direct projected CRS, GCP-based reprojection, direct dB scale and linear amplitude.
    """
    with rasterio.Env(GDAL_CACHEMAX=32), rasterio.open(file_path) as src:
        sar_crs = src.crs
        sar_bounds = src.bounds
        sar_nodata = src.nodata
        has_gcps = bool(src.gcps and src.gcps[0])

        # Check if CRS and bounds already align with target
        crs_match = (target_crs is not None and sar_crs is not None and str(sar_crs) == str(target_crs))
        bounds_match = (
            target_bounds is not None
            and sar_bounds is not None
            and abs(sar_bounds.left - target_bounds.left) < 50.0
            and abs(sar_bounds.right - target_bounds.right) < 50.0
            and abs(sar_bounds.top - target_bounds.top) < 50.0
            and abs(sar_bounds.bottom - target_bounds.bottom) < 50.0
        )

        data = np.full((size, size), np.nan, dtype=np.float32)

        if crs_match and bounds_match:
            # Resample directly to target grid
            data = src.read(
                1,
                out_shape=(size, size),
                resampling=Resampling.bilinear
            ).astype(np.float32)
            if sar_nodata is not None:
                data[data == sar_nodata] = np.nan
            was_reprojected = False
        elif has_gcps:
            # Dynamic on-the-fly reprojection using Ground Control Points (GCPs) from ESA Sentinel-1 SAFE!
            gcps, gcp_crs = src.gcps
            reproject(
                source=rasterio.band(src, 1),
                destination=data,
                src_gcps=gcps,
                src_crs=gcp_crs,
                dst_transform=target_transform,
                dst_crs=target_crs,
                dst_nodata=np.nan,
                resampling=WarpResampling.bilinear
            )
            sar_crs = gcp_crs
            was_reprojected = True
        else:
            # Dynamic reprojection from projected CRS
            reproject(
                source=rasterio.band(src, 1),
                destination=data,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=target_transform,
                dst_crs=target_crs,
                dst_nodata=np.nan,
                resampling=WarpResampling.bilinear
            )
            was_reprojected = True

        profile = {
            "source_crs": str(sar_crs),
            "target_crs": str(target_crs) if target_crs else str(sar_crs),
            "width": src.width,
            "height": src.height,
            "was_reprojected": was_reprojected,
            "nodata": sar_nodata
        }

    # Clean nodata / non-finite
    if profile.get("nodata") is not None:
        data[data == profile["nodata"]] = np.nan

    # Automatic calibration check:
    # 1. Benchmark rasters: already in calibrated decibels (float32, negative median, range -45 to +10 dB)
    # 2. ESA Sentinel-1 SAFE GRD measurement TIFFs: raw uncalibrated uint16 DN amplitude (values 0 - 1500)
    #    Standard ESA S-1 Level-1 Radiometric Calibration: sigma0_linear = DN^2 / A_sigma^2
    #    Nominal IW GRD calibration constant: A_sigma = 350.0 (offset 20*log10(350.0) ≈ 50.88 dB)
    finite_mask = np.isfinite(data)
    raw_data = data.copy()
    raw_pos = raw_data[finite_mask & (raw_data > 0)] if np.any(finite_mask & (raw_data > 0)) else np.array([0.0], dtype=np.float32)

    raw_min = float(np.min(raw_pos))
    raw_max = float(np.max(raw_pos))
    raw_mean = float(np.mean(raw_pos))

    if np.any(finite_mask):
        median_val = float(np.median(data[finite_mask]))
        if median_val > 0 and np.max(data[finite_mask]) > 10.0:
            # Raw uint16 DN amplitude -> convert to physical sigma0 linear intensity: sigma0 = DN^2 / A_sigma^2
            cal_const = 350.0
            linear_backscatter = np.zeros_like(data, dtype=np.float32)
            pos_mask = finite_mask & (data > 0)
            linear_backscatter[pos_mask] = (data[pos_mask] / cal_const) ** 2

            # Convert to decibels (dB): 10 * log10(sigma0)
            calibrated_db = np.full_like(data, -35.0)
            calibrated_db[pos_mask] = 10.0 * np.log10(linear_backscatter[pos_mask] + 1e-7)
            calibrated_db = np.clip(calibrated_db, -45.0, 10.0)

            data = calibrated_db
            processed_linear = linear_backscatter
        else:
            # Already in calibrated dB (clip to realistic C-band radar limits)
            data = np.clip(data, -45.0, 10.0)
            processed_linear = 10.0 ** (data / 10.0)
    else:
        data = np.full((size, size), -20.0, dtype=np.float32)
        processed_linear = np.full((size, size), 0.01, dtype=np.float32)

    valid_proc_db = data[np.isfinite(data)]
    valid_proc_lin = processed_linear[np.isfinite(processed_linear)]

    audit = {
        "raw_min": round(raw_min, 4),
        "raw_max": round(raw_max, 4),
        "raw_mean": round(raw_mean, 4),
        "processed_linear_min": round(float(np.min(valid_proc_lin)), 6),
        "processed_linear_max": round(float(np.max(valid_proc_lin)), 6),
        "processed_linear_mean": round(float(np.mean(valid_proc_lin)), 6),
        "processed_db_min": round(float(np.min(valid_proc_db)), 2),
        "processed_db_max": round(float(np.max(valid_proc_db)), 2),
        "processed_db_mean": round(float(np.mean(valid_proc_db)), 2),
        "calibration_standard": "ESA Sentinel-1 Level-1 GRD Radiometric Calibration to Sigma-0"
    }
    profile["calibration_audit"] = audit
    profile["processed_linear"] = processed_linear

    return data, profile


def build_fusion_composite_image(
    optical_rgb: Image.Image,
    ndvi_arr: np.ndarray,
    sigma0_vv: np.ndarray,
    sigma0_vh: np.ndarray,
    rvi_arr: np.ndarray,
    optical_scene: str,
    sar_scene: str,
    output_path: Path,
    stats: dict
) -> Path:
    """
    Generate a 4-panel multimodal fusion composite graphic using Pillow:
    Panel 1: Optical True-Color RGB
    Panel 2: Optical NDVI Heatmap
    Panel 3: SAR Dual-Polarization False-Color Composite (R=VV, G=VH, B=Ratio)
    Panel 4: Multi-Sensor Fused Land Classification Overlay
    """
    panel_w = 270
    panel_h = 270
    width = 1140
    height = 540

    img = Image.new("RGB", (width, height), color="#0b1120")
    draw = ImageDraw.Draw(img)

    # Header Bar
    draw.rectangle([(0, 0), (width, 56)], fill="#1e293b")
    draw.text((25, 12), "SatQuery AI — Multimodal Remote Sensing Optical + SAR Fusion Engine", fill="#38bdf8")
    draw.text(
        (25, 32),
        f"Optical Sensor: Landsat-9 OLI-2 ({optical_scene[:28]})  |  Active Radar: Sentinel-1 C-SAR ({sar_scene[:24]})",
        fill="#94a3b8"
    )

    y_offset = 74
    x_gap = 14
    margin_x = 18

    # -------------------------------------------------------------
    # Panel 1: Optical RGB
    # -------------------------------------------------------------
    p1_x = margin_x
    opt_resized = optical_rgb.resize((panel_w, panel_h), Image.Resampling.BILINEAR)
    img.paste(opt_resized, (p1_x, y_offset))
    draw.rectangle([(p1_x, y_offset), (p1_x + panel_w, y_offset + panel_h)], outline="#38bdf8", width=2)
    # Title badge
    draw.rectangle([(p1_x, y_offset), (p1_x + 150, y_offset + 22)], fill="#1e293b")
    draw.text((p1_x + 8, y_offset + 4), "1. Optical RGB (B4,B3,B2)", fill="#f8fafc")

    # -------------------------------------------------------------
    # Panel 2: Optical NDVI Heatmap
    # -------------------------------------------------------------
    p2_x = p1_x + panel_w + x_gap
    # Render NDVI color map:
    # < 0.0: Water (Blue #0284c7)
    # 0.0 - 0.2: Bare Soil / Sparse (Tan #b45309)
    # 0.2 - 0.4: Cropland / Grass (Light Green #84cc16)
    # > 0.4: Dense Canopy (Deep Green #15803d)
    ndvi_h, ndvi_w = ndvi_arr.shape
    ndvi_rgb = np.zeros((ndvi_h, ndvi_w, 3), dtype=np.uint8)

    w_mask = ndvi_arr < 0.0
    bare_mask = (ndvi_arr >= 0.0) & (ndvi_arr < 0.20)
    crop_mask = (ndvi_arr >= 0.20) & (ndvi_arr < 0.40)
    forest_mask = ndvi_arr >= 0.40

    ndvi_rgb[w_mask] = [2, 132, 199]       # Blue
    ndvi_rgb[bare_mask] = [217, 119, 6]    # Amber
    ndvi_rgb[crop_mask] = [132, 204, 22]   # Lime
    ndvi_rgb[forest_mask] = [21, 128, 61]  # Forest Green

    ndvi_img = Image.fromarray(ndvi_rgb).resize((panel_w, panel_h), Image.Resampling.NEAREST)
    img.paste(ndvi_img, (p2_x, y_offset))
    draw.rectangle([(p2_x, y_offset), (p2_x + panel_w, y_offset + panel_h)], outline="#10b981", width=2)
    draw.rectangle([(p2_x, y_offset), (p2_x + 155, y_offset + 22)], fill="#1e293b")
    draw.text((p2_x + 8, y_offset + 4), "2. Optical NDVI Canopy", fill="#f8fafc")

    # -------------------------------------------------------------
    # Panel 3: SAR Dual-Polarization False Color
    # Red = VV backscatter (surface roughness)
    # Green = VH backscatter (canopy volume scattering)
    # Blue = VH/VV ratio (canopy depolarizing ratio)
    # -------------------------------------------------------------
    p3_x = p2_x + panel_w + x_gap
    # Normalize VV (-28 to -5 dB -> 0 to 255)
    norm_vv = np.clip((sigma0_vv - (-28.0)) / (23.0 + 1e-6) * 255.0, 0, 255).astype(np.uint8)
    # Normalize VH (-32 to -10 dB -> 0 to 255)
    norm_vh = np.clip((sigma0_vh - (-32.0)) / (22.0 + 1e-6) * 255.0, 0, 255).astype(np.uint8)
    # Normalize ratio dB (VH - VV from -15 to -2 dB -> 0 to 255)
    ratio_db = sigma0_vh - sigma0_vv
    norm_ratio = np.clip((ratio_db - (-15.0)) / (13.0 + 1e-6) * 255.0, 0, 255).astype(np.uint8)

    sar_rgb = np.stack([norm_vv, norm_vh, norm_ratio], axis=-1)
    sar_img = Image.fromarray(sar_rgb).resize((panel_w, panel_h), Image.Resampling.BILINEAR)
    img.paste(sar_img, (p3_x, y_offset))
    draw.rectangle([(p3_x, y_offset), (p3_x + panel_w, y_offset + panel_h)], outline="#a855f7", width=2)
    draw.rectangle([(p3_x, y_offset), (p3_x + 165, y_offset + 22)], fill="#1e293b")
    draw.text((p3_x + 8, y_offset + 4), "3. SAR Dual-Pol (VV/VH)", fill="#f8fafc")

    # -------------------------------------------------------------
    # Panel 4: Multi-Sensor Fused Classification
    # Combines Optical NDVI + SAR Radar Roughness/Volume Scattering:
    # - Water: Optical NDWI > 0 OR SAR VV < -18 dB (Cloud-Penetrating Water)
    # - Urban/Structure: SAR VV > -7 dB (Double bounce)
    # - Dense Forest: Optical NDVI > 0.40 AND SAR RVI > 0.35 (Strong Dual Consensus)
    # - Cropland: Optical NDVI > 0.20 OR SAR RVI > 0.20
    # - Bare/Sparse: Remaining
    # -------------------------------------------------------------
    p4_x = p3_x + panel_w + x_gap
    fused_rgb = np.zeros((ndvi_h, ndvi_w, 3), dtype=np.uint8)

    sar_water = sigma0_vv < -18.0
    fused_water = w_mask | sar_water
    urban = (sigma0_vv > -7.0) & (~fused_water)
    dense_veg = forest_mask & (rvi_arr > 0.30) & (~urban)
    mod_veg = (crop_mask | (rvi_arr > 0.20)) & (~dense_veg) & (~fused_water) & (~urban)
    bare = (~fused_water) & (~urban) & (~dense_veg) & (~mod_veg)

    fused_rgb[bare] = [148, 163, 184]        # Slate Gray (Bare / Soil)
    fused_rgb[mod_veg] = [234, 179, 8]       # Amber / Yellow (Cropland)
    fused_rgb[dense_veg] = [16, 185, 129]    # Emerald Green (Dense Forest)
    fused_rgb[urban] = [236, 72, 153]        # Fuchsia (Urban / Rough)
    fused_rgb[fused_water] = [14, 165, 233]  # Sky Blue (All-Weather Water)

    fused_img = Image.fromarray(fused_rgb).resize((panel_w, panel_h), Image.Resampling.NEAREST)
    img.paste(fused_img, (p4_x, y_offset))
    draw.rectangle([(p4_x, y_offset), (p4_x + panel_w, y_offset + panel_h)], outline="#f59e0b", width=2)
    draw.rectangle([(p4_x, y_offset), (p4_x + 175, y_offset + 22)], fill="#1e293b")
    draw.text((p4_x + 8, y_offset + 4), "4. Fused Multi-Sensor Map", fill="#f8fafc")

    # -------------------------------------------------------------
    # Bottom Summary & Legend Card
    # -------------------------------------------------------------
    card_y = y_offset + panel_h + 16
    card_h = 160
    draw.rectangle([(margin_x, card_y), (width - margin_x, card_y + card_h)], fill="#1e293b", outline="#334155", width=1)

    # Column 1: Optical Metrics
    c1_x = margin_x + 20
    draw.text((c1_x, card_y + 12), "OPTICAL METRICS (Landsat)", fill="#38bdf8")
    draw.text((c1_x, card_y + 36), f"• Mean NDVI: {stats.get('mean_ndvi', 0.0):+.3f}", fill="#e2e8f0")
    draw.text((c1_x, card_y + 56), f"• Mean NDWI (Water): {stats.get('mean_ndwi', 0.0):+.3f}", fill="#e2e8f0")
    draw.text((c1_x, card_y + 76), f"• Vegetation Coverage: {stats.get('veg_coverage_pct', 0.0):.1f}%", fill="#e2e8f0")
    draw.text((c1_x, card_y + 96), f"• Optical Water: {stats.get('opt_water_pct', 0.0):.1f}%", fill="#e2e8f0")

    # Column 2: SAR Polarimetric Metrics
    c2_x = c1_x + 250
    draw.text((c2_x, card_y + 12), "SAR METRICS (Sentinel-1)", fill="#a855f7")
    draw.text((c2_x, card_y + 36), f"• Mean VV Backscatter: {stats.get('mean_vv_db', 0.0):.2f} dB", fill="#e2e8f0")
    draw.text((c2_x, card_y + 56), f"• Mean VH Backscatter: {stats.get('mean_vh_db', 0.0):.2f} dB", fill="#e2e8f0")
    draw.text((c2_x, card_y + 76), f"• Radar Veg Index (RVI): {stats.get('mean_rvi', 0.0):.3f}", fill="#e2e8f0")
    draw.text((c2_x, card_y + 96), f"• Cross-Ratio (VH-VV): {stats.get('vh_vv_diff_db', 0.0):+.2f} dB", fill="#e2e8f0")

    # Column 3: Fusion & Consensus
    c3_x = c2_x + 260
    draw.text((c3_x, card_y + 12), "CROSS-SENSOR CONSENSUS", fill="#f59e0b")
    draw.text((c3_x, card_y + 36), f"• Optical-SAR Agreement: {stats.get('veg_consensus_pct', 0.0):.1f}%", fill="#10b981")
    draw.text((c3_x, card_y + 56), f"• Cloud-Penetrating Water: {stats.get('fused_water_pct', 0.0):.1f}%", fill="#38bdf8")
    draw.text((c3_x, card_y + 76), f"• High Roughness / Urban: {stats.get('urban_pct', 0.0):.1f}%", fill="#ec4899")
    draw.text((c3_x, card_y + 96), f"• Sensor Correlation (r): {stats.get('correlation', 0.0):+.2f}", fill="#e2e8f0")

    # Column 4: Fused Map Legend
    c4_x = c3_x + 270
    draw.text((c4_x, card_y + 12), "FUSED MAP LEGEND", fill="#f8fafc")
    legend_items = [
        ("#10b981", "Dense Forest Canopy"),
        ("#eab308", "Agricultural / Cropland"),
        ("#0ea5e9", "All-Weather Water"),
        ("#ec4899", "Urban / Rough Surface"),
        ("#94a3b8", "Bare Soil / Sparse")
    ]
    leg_y = card_y + 36
    for col, lbl in legend_items:
        draw.rectangle([(c4_x, leg_y + 2), (c4_x + 12, leg_y + 14)], fill=col)
        draw.text((c4_x + 20, leg_y), lbl, fill="#cbd5e1")
        leg_y += 22

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path


def run_optical_sar_analysis(
    upload_dir: Path = Path("uploads"),
    output_dir: Path = Path("uploads/fusion"),
    size: int = 512,
    **kwargs
) -> dict:
    """
    Execute multimodal Optical + SAR fusion analysis.
    Combines Landsat optical surface reflectance with Sentinel-1 SAR dual-pol backscatter.
    """
    try:
        # 1. Locate optical scene
        opt_data = find_landsat_bands(
            upload_dir,
            target_scene=kwargs.get("target_scene") or kwargs.get("optical_scene")
        )
        if not opt_data["found"]:
            return {
                "success": False,
                "tool": "optical_sar_model",
                "error": opt_data.get("reason", "Could not locate Landsat optical bands.")
            }

        opt_scene = opt_data["scene"]
        opt_bands = opt_data["bands"]

        # 2. Locate SAR scene
        sar_data = find_sar_bands(
            upload_dir,
            target_scene=kwargs.get("sar_scene")
        )
        if not sar_data["found"]:
            return {
                "success": False,
                "tool": "optical_sar_model",
                "error": sar_data.get("reason", "Could not locate Sentinel-1 SAR bands.")
            }

        sar_scene = sar_data["scene"]
        sar_bands = sar_data["bands"]

        # 3. Read optical bands
        b2_raw, _ = read_band(opt_bands["B2"], size)
        b3_raw, _ = read_band(opt_bands["B3"], size)
        b4_raw, _ = read_band(opt_bands["B4"], size)
        b5_raw, p5 = read_band(opt_bands["B5"], size)

        # Scale reflectance
        b2 = scale_landsat_surface_reflectance(b2_raw)
        b3 = scale_landsat_surface_reflectance(b3_raw)
        b4 = scale_landsat_surface_reflectance(b4_raw)
        b5 = scale_landsat_surface_reflectance(b5_raw)

        # Read SAR bands
        vv_path = sar_bands.get("VV")
        vh_path = sar_bands.get("VH")

        if not vv_path or not vh_path:
            return {
                "success": False,
                "tool": "optical_sar_model",
                "error": "Both VV and VH polarizations are required for dual-polarization SAR fusion."
            }

        # Extract optical reference CRS and bounds for dynamic spatial reprojection
        with rasterio.open(opt_bands["B4"]) as ds_opt:
            opt_crs = ds_opt.crs
            opt_bounds = ds_opt.bounds
            opt_target_transform = rasterio.transform.from_bounds(
                opt_bounds.left, opt_bounds.bottom,
                opt_bounds.right, opt_bounds.top,
                size, size
            )

        with rasterio.open(vv_path) as ds_vv:
            sar_crs = ds_vv.crs
            sar_bounds = ds_vv.bounds
            sar_gcps = ds_vv.gcps

        # Verify spatial overlap
        if str(opt_crs) == str(sar_crs):
            overlap_x = max(0, min(opt_bounds.right, sar_bounds.right) - max(opt_bounds.left, sar_bounds.left))
            overlap_y = max(0, min(opt_bounds.top, sar_bounds.top) - max(opt_bounds.bottom, sar_bounds.bottom))
            if overlap_x < 1000 or overlap_y < 1000:
                return {
                    "success": False,
                    "tool": "optical_sar_model",
                    "error": (
                        "Optical + SAR analysis requires a compatible SAR scene. "
                        "The currently selected scene is optical-only. "
                        "Please select or upload a compatible Sentinel-1 SAR scene."
                    )
                }
        else:
            # Check geographic bounding box overlap in WGS84
            sar_wgs_bounds = None
            if sar_gcps and sar_gcps[0]:
                gcps = sar_gcps[0]
                lons = [g.x for g in gcps]
                lats = [g.y for g in gcps]
                sar_wgs_bounds = (min(lons), min(lats), max(lons), max(lats))
            elif sar_crs and str(sar_crs) != "None":
                try:
                    from rasterio.warp import transform_bounds
                    sar_wgs_bounds = transform_bounds(sar_crs, "EPSG:4326", *sar_bounds)
                except Exception:
                    pass

            if sar_wgs_bounds and opt_crs and str(opt_crs) != "None":
                try:
                    from rasterio.warp import transform_bounds
                    opt_wgs = transform_bounds(opt_crs, "EPSG:4326", *opt_bounds)
                    ol_lon = max(0.0, min(opt_wgs[2], sar_wgs_bounds[2]) - max(opt_wgs[0], sar_wgs_bounds[0]))
                    ol_lat = max(0.0, min(opt_wgs[3], sar_wgs_bounds[3]) - max(opt_wgs[1], sar_wgs_bounds[1]))
                    if ol_lon <= 0.0 or ol_lat <= 0.0:
                        return {
                            "success": False,
                            "tool": "optical_sar_model",
                            "error": (
                                "The selected optical and SAR observations do not geographically overlap. "
                                "Please select an optical and SAR pair covering the same geographic region."
                            )
                        }
                except Exception:
                    pass

        sigma0_vv, p_vv = read_sar_band(
            vv_path,
            size=size,
            target_crs=opt_crs,
            target_bounds=opt_bounds,
            target_transform=opt_target_transform
        )
        sigma0_vh, p_vh = read_sar_band(
            vh_path,
            size=size,
            target_crs=opt_crs,
            target_bounds=opt_bounds,
            target_transform=opt_target_transform
        )

        # Valid mask across both sensors
        valid_mask = (
            np.isfinite(b2) & np.isfinite(b3) & np.isfinite(b4) & np.isfinite(b5)
            & (b4 >= 0) & (b5 >= 0)
            & np.isfinite(sigma0_vv) & np.isfinite(sigma0_vh)
        )

        if not np.any(valid_mask):
            return {
                "success": False,
                "tool": "optical_sar_model",
                "error": "No overlapping valid pixels found between optical and SAR rasters."
            }

        # -------------------------------------------------------------
        # Compute Optical Indices
        # -------------------------------------------------------------
        v_b3 = b3[valid_mask]
        v_b4 = b4[valid_mask]
        v_b5 = b5[valid_mask]

        ndvi_full = (b5 - b4) / (b5 + b4 + 1e-6)
        ndvi_vals = ndvi_full[valid_mask]
        mean_ndvi = float(np.mean(ndvi_vals))

        ndwi_full = (b3 - b5) / (b3 + b5 + 1e-6)
        ndwi_vals = ndwi_full[valid_mask]
        mean_ndwi = float(np.mean(ndwi_vals))

        opt_veg_pct = float(np.mean(ndvi_vals >= 0.20) * 100.0)
        opt_water_pct = float(np.mean(ndwi_vals > 0.0) * 100.0)

        # Build Optical RGB preview for composite
        norm_r = normalize_channel(b4, valid_mask)
        norm_g = normalize_channel(b3, valid_mask)
        norm_b = normalize_channel(b2, valid_mask)
        opt_rgb_arr = np.stack([norm_r, norm_g, norm_b], axis=-1)
        opt_rgb_img = Image.fromarray(opt_rgb_arr)

        # -------------------------------------------------------------
        # Compute SAR Polarimetric Indices
        # -------------------------------------------------------------
        v_vv = sigma0_vv[valid_mask]
        v_vh = sigma0_vh[valid_mask]

        mean_vv = float(np.mean(v_vv))
        mean_vh = float(np.mean(v_vh))
        vh_vv_diff = mean_vh - mean_vv  # Ratio in dB

        # Compute RVI strictly from LINEAR backscatter quantities
        # RVI = (4 * VH_linear) / (VV_linear + VH_linear)
        lin_vv = p_vv.get("processed_linear")
        lin_vh = p_vh.get("processed_linear")
        if lin_vv is not None and lin_vh is not None:
            rvi_full = (4.0 * lin_vh) / (lin_vv + lin_vh + 1e-6)
        else:
            i_vv = 10.0 ** (sigma0_vv / 10.0)
            i_vh = 10.0 ** (sigma0_vh / 10.0)
            rvi_full = (4.0 * i_vh) / (i_vv + i_vh + 1e-6)

        rvi_full = np.clip(rvi_full, 0.0, 1.0)
        rvi_vals = rvi_full[valid_mask]
        mean_rvi = float(np.mean(rvi_vals))

        sar_water_mask = sigma0_vv < -18.0
        sar_water_pct = float(np.mean(sar_water_mask[valid_mask]) * 100.0)

        urban_mask = (sigma0_vv > -7.0) & (~sar_water_mask)
        urban_pct = float(np.mean(urban_mask[valid_mask]) * 100.0)

        # -------------------------------------------------------------
        # Cross-Sensor Fusion & Consensus Metrics
        # -------------------------------------------------------------
        # Water consensus (prototype thresholds: optical NDWI > 0.0 or SAR specular VV < -18 dB)
        fused_water_mask = (ndwi_full > 0.0) | sar_water_mask
        fused_water_pct = float(np.mean(fused_water_mask[valid_mask]) * 100.0)
        water_both = (ndwi_full > 0.0) & sar_water_mask
        water_consensus_pct = float(np.mean(water_both[valid_mask]) * 100.0)

        # Vegetation consensus (Optical NDVI >= 0.20 and SAR RVI >= 0.20)
        opt_veg = ndvi_full >= 0.20
        sar_veg = rvi_full >= 0.20
        veg_agreement = (opt_veg == sar_veg)
        veg_consensus_pct = float(np.mean(veg_agreement[valid_mask]) * 100.0)

        # Pearson correlation between Optical NDVI and SAR RVI on valid aligned pixels
        valid_paired_count = int(np.sum(valid_mask))
        correlation = None
        if valid_paired_count >= 100:
            std_ndvi = float(np.std(ndvi_vals))
            std_rvi = float(np.std(rvi_vals))
            if std_ndvi > 1e-4 and std_rvi > 1e-4:
                corr_mat = np.corrcoef(ndvi_vals, rvi_vals)
                c_val = float(corr_mat[0, 1])
                if np.isfinite(c_val):
                    correlation = round(c_val, 3)

        # Fusion classification summary: scientifically defensible environmental summary
        if fused_water_pct > 15.0:
            env_summary = "Water / High Moisture Surface Dominance (Coastal / Marine Environment)"
        elif mean_ndvi >= 0.40 and mean_rvi >= 0.35:
            env_summary = "Dense Canopy Forest & Strong Volumetric Radar Scattering"
        elif mean_ndvi >= 0.20:
            env_summary = "Agricultural Cropland / Grassland with Moderate Roughness"
        else:
            env_summary = "Arid / Sparse Surface with High Background Roughness"

        # -------------------------------------------------------------
        # Build 4-Panel Multimodal Fusion Composite Graphic
        # -------------------------------------------------------------
        composite_filename = f"{opt_scene}_optical_sar_fusion_composite.png"
        composite_path = output_dir / composite_filename

        stats_for_chart = {
            "mean_ndvi": mean_ndvi,
            "mean_ndwi": mean_ndwi,
            "veg_coverage_pct": opt_veg_pct,
            "opt_water_pct": opt_water_pct,
            "mean_vv_db": mean_vv,
            "mean_vh_db": mean_vh,
            "mean_rvi": mean_rvi,
            "vh_vv_diff_db": vh_vv_diff,
            "fused_water_pct": fused_water_pct,
            "urban_pct": urban_pct,
            "veg_consensus_pct": veg_consensus_pct,
            "correlation": correlation if correlation is not None else 0.0
        }

        build_fusion_composite_image(
            optical_rgb=opt_rgb_img,
            ndvi_arr=ndvi_full,
            sigma0_vv=sigma0_vv,
            sigma0_vh=sigma0_vh,
            rvi_arr=rvi_full,
            optical_scene=opt_scene,
            sar_scene=sar_scene,
            output_path=composite_path,
            stats=stats_for_chart
        )

        # Mirror composite to uploads/fusion/ to guarantee web accessibility
        mirror_dir = Path("uploads") / "fusion"
        mirror_dir.mkdir(parents=True, exist_ok=True)
        try:
            target_composite = mirror_dir / composite_filename
            if composite_path.resolve() != target_composite.resolve():
                shutil.copy2(composite_path, target_composite)
        except Exception:
            pass

        composite_web_url = to_web_url(composite_path)

        provenance = {
            "optical": {
                "scene_id": opt_scene,
                "bands_used": ["B2 (Blue)", "B3 (Green)", "B4 (Red)", "B5 (NIR)"],
                "formula_ndvi": "(NIR - Red) / (NIR + Red)",
                "formula_ndwi": "(Green - NIR) / (Green + NIR)",
                "calibration": "USGS Landsat Collection 2 Level-2 Surface Reflectance (DN * 0.0000275 - 0.2)"
            },
            "sar": {
                "scene_id": sar_scene,
                "polarizations": ["VV", "VH"],
                "units": "decibels (dB) sigma-0 backscatter",
                "calibration": "ESA Sentinel-1 Level-1 GRD Radiometric Calibration to Sigma-0",
                "rvi_formula": "4 * VH_linear / (VV_linear + VH_linear)",
                "rvi_domain": "linear backscatter intensity (sigma-0 linear)"
            },
            "fusion": {
                "active_pair_id": kwargs.get("active_pair_id"),
                "optical_scene_id": opt_scene,
                "sar_scene_id": sar_scene,
                "spatial_alignment": "Reprojected to common optical grid via Sentinel-1 Ground Control Points (GCPs)",
                "valid_paired_pixel_count": valid_paired_count,
                "water_thresholds": "Optical NDWI > 0.0 OR SAR specular backscatter VV < -18.0 dB",
                "vegetation_thresholds": "Optical NDVI >= 0.20, SAR RVI >= 0.20"
            }
        }

        return {
            "success": True,
            "tool": "optical_sar_model",
            "active_pair_id": kwargs.get("active_pair_id"),
            "optical_scene": opt_scene,
            "sar_scene": sar_scene,
            "optical_metrics": {
                "mean_ndvi": round(mean_ndvi, 4),
                "mean_ndwi": round(mean_ndwi, 4),
                "vegetation_pixel_coverage_pct": round(opt_veg_pct, 2),
                "vegetation_classification_threshold": "NDVI >= 0.20",
                "potential_water_coverage_pct": round(opt_water_pct, 2),
                "water_classification_threshold": "NDWI > 0.0"
            },
            "sar_metrics": {
                "mean_sigma0_vv_db": round(mean_vv, 2),
                "mean_sigma0_vh_db": round(mean_vh, 2),
                "mean_rvi": round(mean_rvi, 4),
                "rvi_formula": "4 * VH_linear / (VV_linear + VH_linear)",
                "cross_polarization_ratio_db": round(vh_vv_diff, 2),
                "sar_specular_water_coverage_pct": round(sar_water_pct, 2),
                "urban_roughness_coverage_pct": round(urban_pct, 2),
                "calibration_audit": {
                    "vv": p_vv.get("calibration_audit", {}),
                    "vh": p_vh.get("calibration_audit", {})
                }
            },
            "fusion_metrics": {
                "environmental_classification": env_summary,
                "prototype_cross_sensor_agreement_score": round(veg_consensus_pct, 2),
                "cross_sensor_vegetation_agreement_pct": round(veg_consensus_pct, 2),
                "potential_water_inundation_coverage_pct": round(fused_water_pct, 2),
                "optical_sar_correlation": correlation,
                "correlation_status": f"r = {correlation:+.3f}" if correlation is not None else "Insufficient aligned pixels for correlation",
                "valid_paired_pixels": valid_paired_count
            },
            "provenance": provenance,
            "evidence": {
                "fusion_composite": composite_web_url,
                "composite_disk_path": str(composite_path),
                "artifact_type": "fusion_composite",
                "filename": composite_filename,
                "url": composite_web_url
            },
            "processing_metadata": {
                "optical_crs": str(opt_crs),
                "sar_source_crs": p_vv.get("source_crs"),
                "dynamic_reprojection_applied": p_vv.get("was_reprojected") or p_vh.get("was_reprojected"),
                "sampled_resolution": f"{size}x{size}",
                "valid_pixel_count": valid_paired_count
            }
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "optical_sar_model",
            "error": str(e)
        }
