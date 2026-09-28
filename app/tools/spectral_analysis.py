import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import shutil
from app.services.multispectral_processor import (
    find_landsat_bands,
    read_band,
    scale_landsat_surface_reflectance,
    to_web_url
)

def get_sensor_band_info(scene_name: str) -> tuple[str, dict]:
    """
    Return sensor identity and calibrated band metadata (central wavelength in µm).
    Distinguishes Landsat-8/9 OLI/OLI-2 from Sentinel-2 MSI and generic sensors.
    """
    name_upper = scene_name.upper()
    if "LC08" in name_upper or "LC09" in name_upper:
        sensor = "Landsat-8/9 OLI-2"
        band_dict = {
            "B2": {"name": "Blue", "wavelength": 0.482, "color": "#3b82f6"},
            "B3": {"name": "Green", "wavelength": 0.562, "color": "#10b981"},
            "B4": {"name": "Red", "wavelength": 0.655, "color": "#ef4444"},
            "B5": {"name": "Near-Infrared (NIR)", "wavelength": 0.865, "color": "#8b5cf6"}
        }
    elif "S2" in name_upper or "SENTINEL" in name_upper:
        sensor = "Sentinel-2 MSI"
        band_dict = {
            "B2": {"name": "Blue", "wavelength": 0.490, "color": "#3b82f6"},
            "B3": {"name": "Green", "wavelength": 0.560, "color": "#10b981"},
            "B4": {"name": "Red", "wavelength": 0.665, "color": "#ef4444"},
            "B5": {"name": "NIR (B8/B8A)", "wavelength": 0.842, "color": "#8b5cf6"}
        }
    else:
        sensor = "Calibrated Multispectral Optical Sensor"
        band_dict = {
            "B2": {"name": "Blue", "wavelength": 0.480, "color": "#3b82f6"},
            "B3": {"name": "Green", "wavelength": 0.560, "color": "#10b981"},
            "B4": {"name": "Red", "wavelength": 0.650, "color": "#ef4444"},
            "B5": {"name": "Near-Infrared (NIR)", "wavelength": 0.860, "color": "#8b5cf6"}
        }
    return sensor, band_dict


BAND_INFO = {
    "B2": {"name": "Blue", "wavelength": 0.48, "color": "#3b82f6"},
    "B3": {"name": "Green", "wavelength": 0.56, "color": "#10b981"},
    "B4": {"name": "Red", "wavelength": 0.65, "color": "#ef4444"},
    "B5": {"name": "Near-Infrared (NIR)", "wavelength": 0.86, "color": "#8b5cf6"}
}


def draw_spectral_profile_chart(
    scene_name: str,
    band_means: dict,
    ndwi_val: float,
    ndvi_val: float,
    output_path: Path
) -> Path:
    """
    Draw a clean, dark-themed spectral reflectance profile chart using Pillow.
    Plots Surface Reflectance vs. Spectral Wavelength (µm) across B2, B3, B4, and B5.
    """
    sensor_title, band_info = get_sensor_band_info(scene_name)

    width = 800
    height = 460
    img = Image.new("RGB", (width, height), color="#0f172a")
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([(0, 0), (width, 50)], fill="#1e293b")
    draw.text((25, 14), f"SatQuery AI — {sensor_title} Reflectance Profile: {scene_name[:30]}", fill="#38bdf8")

    # Chart boundaries
    chart_x0 = 80
    chart_y0 = 80
    chart_x1 = 520
    chart_y1 = 390

    # Draw grid and background
    draw.rectangle([(chart_x0, chart_y0), (chart_x1, chart_y1)], fill="#090d16", outline="#334155", width=2)

    # Determine max Y scale
    max_ref = max([v for v in band_means.values() if v is not None] + [0.35])
    y_max = math.ceil(max_ref * 10) / 10.0
    if y_max < 0.3:
        y_max = 0.3

    # Y-axis ticks and labels
    for i in range(5):
        val = y_max * (i / 4.0)
        y_pos = int(chart_y1 - (i / 4.0) * (chart_y1 - chart_y0))
        draw.line([(chart_x0, y_pos), (chart_x1, y_pos)], fill="#1e293b", width=1)
        draw.text((chart_x0 - 45, y_pos - 7), f"{val:.2f}", fill="#94a3b8")

    # Y-axis label
    draw.text((chart_x0 - 70, chart_y0 - 25), "Surface Reflectance", fill="#cbd5e1")

    # X-axis mapping (Wavelengths 0.40 µm to 0.95 µm)
    wl_min = 0.40
    wl_max = 0.95

    def wl_to_x(wl):
        return int(chart_x0 + ((wl - wl_min) / (wl_max - wl_min)) * (chart_x1 - chart_x0))

    def ref_to_y(ref):
        clamped = max(0.0, min(ref, y_max))
        return int(chart_y1 - (clamped / y_max) * (chart_y1 - chart_y0))

    # Points for spectral curve
    points = []
    band_keys = ["B2", "B3", "B4", "B5"]
    for b in band_keys:
        val = band_means.get(b, 0.0)
        wl = band_info[b]["wavelength"]
        x = wl_to_x(wl)
        y = ref_to_y(val)
        points.append((x, y, b, val, wl))

    # Draw curve lines
    for i in range(len(points) - 1):
        x1, y1, _, _, _ = points[i]
        x2, y2, _, _, _ = points[i + 1]
        draw.line([(x1, y1), (x2, y2)], fill="#38bdf8", width=3)

    # Draw point markers and X-axis ticks
    for x, y, b, val, wl in points:
        color = band_info[b]["color"]
        # Vertical dashed grid line
        draw.line([(x, chart_y0), (x, chart_y1)], fill="#1e293b", width=1)
        # Marker circle
        r = 6
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=color, outline="#ffffff", width=2)
        # Value tag above marker
        draw.text((x - 14, y - 20), f"{val:.3f}", fill="#f8fafc")
        # X tick label
        draw.text((x - 10, chart_y1 + 8), f"{b}", fill=color)
        draw.text((x - 18, chart_y1 + 22), f"{wl}µm", fill="#94a3b8")

    # X-axis title
    draw.text((int((chart_x0 + chart_x1) / 2) - 50, chart_y1 + 42), "Wavelength (µm)", fill="#cbd5e1")

    # Right side: Metric cards & Legend
    panel_x = 550
    draw.rectangle([(panel_x, chart_y0), (width - 25, chart_y1 + 45)], fill="#1e293b", outline="#334155", width=1)
    draw.text((panel_x + 15, chart_y0 + 15), "SPECTRAL SUMMARY", fill="#f8fafc")

    draw.line([(panel_x + 15, chart_y0 + 38), (width - 40, chart_y0 + 38)], fill="#334155", width=1)

    # Band listings
    y_entry = chart_y0 + 50
    for b in band_keys:
        info = band_info[b]
        mean_v = band_means.get(b, 0.0)
        draw.rectangle([(panel_x + 15, y_entry + 3), (panel_x + 27, y_entry + 15)], fill=info["color"])
        draw.text((panel_x + 35, y_entry), f"{b} ({info['name']}):", fill="#cbd5e1")
        draw.text((panel_x + 160, y_entry), f"{mean_v:.3f}", fill="#ffffff")
        y_entry += 28

    draw.line([(panel_x + 15, y_entry + 5), (width - 40, y_entry + 5)], fill="#334155", width=1)
    y_entry += 18

    # Key indices
    draw.text((panel_x + 15, y_entry), "Mean NDVI (Vegetation):", fill="#cbd5e1")
    draw.text((panel_x + 160, y_entry), f"{ndvi_val:+.3f}", fill="#10b981")
    y_entry += 28

    draw.text((panel_x + 15, y_entry), "NDWI (McFeeters '96):", fill="#cbd5e1")
    draw.text((panel_x + 160, y_entry), f"{ndwi_val:+.3f}", fill="#38bdf8")
    y_entry += 28

    nir_red_ratio = (band_means.get("B5", 0.0) / (band_means.get("B4", 0.001) + 1e-6))
    draw.text((panel_x + 15, y_entry), "NIR / Red Ratio:", fill="#cbd5e1")
    draw.text((panel_x + 160, y_entry), f"{nir_red_ratio:.2f}", fill="#8b5cf6")
    y_entry += 34

    # Environmental signature badge
    if ndwi_val > 0.0:
        surface_type = "Surface Water Dominant"
        badge_col = "#0284c7"
    elif ndvi_val >= 0.35:
        surface_type = "Vigorous Green Canopy"
        badge_col = "#059669"
    elif ndvi_val >= 0.15:
        surface_type = "Moderate Grass/Cropland"
        badge_col = "#d97706"
    else:
        surface_type = "Arid / Sparse / Rock"
        badge_col = "#64748b"

    draw.rectangle([(panel_x + 15, y_entry), (width - 40, y_entry + 32)], fill=badge_col)
    draw.text((panel_x + 25, y_entry + 8), surface_type, fill="#ffffff")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path


def compute_chunked_spectral_statistics(
    bands: dict,
    band_info: dict,
    chunk_size: int = 1024
) -> dict:
    """
    Compute full-resolution scientific per-band statistics (B2, B3, B4, B5)
    and spectral indices (NDWI, NDVI, SR) across bounded windowed chunks (1024x1024).
    Never loads complete high-resolution 7591x7751 rasters into RAM.
    Accumulates count, sum, sum_of_squares, min, max incrementally.
    """
    import rasterio
    from rasterio.windows import Window
    import gc

    b_names = ["B2", "B3", "B4", "B5"]
    accumulators = {
        b: {"count": 0, "sum": 0.0, "sum_sq": 0.0, "min": float("inf"), "max": float("-inf")}
        for b in b_names
    }
    ndvi_accum = {"count": 0, "sum": 0.0, "sum_sq": 0.0, "min": float("inf"), "max": float("-inf"), "gt_02": 0}
    ndwi_accum = {"count": 0, "sum": 0.0, "sum_sq": 0.0, "min": float("inf"), "max": float("-inf"), "gt_0": 0}
    sr_accum = {"count": 0, "sum": 0.0}

    with rasterio.Env(GDAL_CACHEMAX=32):
        with rasterio.open(bands["B2"]) as ds2, \
             rasterio.open(bands["B3"]) as ds3, \
             rasterio.open(bands["B4"]) as ds4, \
             rasterio.open(bands["B5"]) as ds5:

            width = min(ds2.width, ds3.width, ds4.width, ds5.width)
            height = min(ds2.height, ds3.height, ds4.height, ds5.height)
            crs_str = str(ds2.crs)

            nodata2 = ds2.nodata
            nodata3 = ds3.nodata
            nodata4 = ds4.nodata
            nodata5 = ds5.nodata

            for row_off in range(0, height, chunk_size):
                h_chunk = min(chunk_size, height - row_off)
                for col_off in range(0, width, chunk_size):
                    w_chunk = min(chunk_size, width - col_off)
                    win = Window(col_off, row_off, w_chunk, h_chunk)

                    raw2 = ds2.read(1, window=win).astype(np.float32)
                    raw3 = ds3.read(1, window=win).astype(np.float32)
                    raw4 = ds4.read(1, window=win).astype(np.float32)
                    raw5 = ds5.read(1, window=win).astype(np.float32)

                    sr2 = (raw2 * 0.0000275) - 0.2
                    sr3 = (raw3 * 0.0000275) - 0.2
                    sr4 = (raw4 * 0.0000275) - 0.2
                    sr5 = (raw5 * 0.0000275) - 0.2

                    valid = (
                        (raw2 != nodata2 if nodata2 is not None else raw2 > 0)
                        & (raw3 != nodata3 if nodata3 is not None else raw3 > 0)
                        & (raw4 != nodata4 if nodata4 is not None else raw4 > 0)
                        & (raw5 != nodata5 if nodata5 is not None else raw5 > 0)
                        & (raw2 > 0) & (raw3 > 0) & (raw4 > 0) & (raw5 > 0)
                        & np.isfinite(sr2) & np.isfinite(sr3) & np.isfinite(sr4) & np.isfinite(sr5)
                        & (sr2 >= 0.0) & (sr3 >= 0.0) & (sr4 >= 0.0) & (sr5 >= 0.0)
                    )

                    if np.any(valid):
                        v2 = sr2[valid]
                        v3 = sr3[valid]
                        v4 = sr4[valid]
                        v5 = sr5[valid]
                        n = v2.size

                        for b_key, v_arr in [("B2", v2), ("B3", v3), ("B4", v4), ("B5", v5)]:
                            acc = accumulators[b_key]
                            acc["count"] += n
                            acc["sum"] += float(np.sum(v_arr))
                            acc["sum_sq"] += float(np.sum(v_arr ** 2))
                            acc["min"] = min(acc["min"], float(np.min(v_arr)))
                            acc["max"] = max(acc["max"], float(np.max(v_arr)))

                        # NDVI = (NIR - Red) / (NIR + Red)
                        denom_ndvi = v5 + v4 + 1e-6
                        ndvi_chunk = (v5 - v4) / denom_ndvi
                        ndvi_accum["count"] += n
                        ndvi_accum["sum"] += float(np.sum(ndvi_chunk))
                        ndvi_accum["sum_sq"] += float(np.sum(ndvi_chunk ** 2))
                        ndvi_accum["min"] = min(ndvi_accum["min"], float(np.min(ndvi_chunk)))
                        ndvi_accum["max"] = max(ndvi_accum["max"], float(np.max(ndvi_chunk)))
                        ndvi_accum["gt_02"] += int(np.sum(ndvi_chunk > 0.20))

                        # NDWI = (Green - NIR) / (Green + NIR)
                        denom_ndwi = v3 + v5 + 1e-6
                        ndwi_chunk = (v3 - v5) / denom_ndwi
                        ndwi_accum["count"] += n
                        ndwi_accum["sum"] += float(np.sum(ndwi_chunk))
                        ndwi_accum["sum_sq"] += float(np.sum(ndwi_chunk ** 2))
                        ndwi_accum["min"] = min(ndwi_accum["min"], float(np.min(ndwi_chunk)))
                        ndwi_accum["max"] = max(ndwi_accum["max"], float(np.max(ndwi_chunk)))
                        ndwi_accum["gt_0"] += int(np.sum(ndwi_chunk > 0.0))

                        # SR = NIR / Red
                        sr_chunk = v5 / (v4 + 1e-6)
                        sr_accum["count"] += n
                        sr_accum["sum"] += float(np.sum(sr_chunk))

                    del raw2, raw3, raw4, raw5, sr2, sr3, sr4, sr5, valid

    gc.collect()

    band_stats = {}
    band_means = {}

    for b_name in b_names:
        acc = accumulators[b_name]
        if acc["count"] > 0:
            m = acc["sum"] / acc["count"]
            v = max(0.0, (acc["sum_sq"] / acc["count"]) - (m ** 2))
            s = math.sqrt(v)
            band_means[b_name] = m
            band_stats[b_name] = {
                "band_name": band_info[b_name]["name"],
                "wavelength_microns": band_info[b_name]["wavelength"],
                "mean_reflectance": round(m, 4),
                "stddev": round(s, 4),
                "min": round(acc["min"], 4),
                "max": round(acc["max"], 4)
            }
        else:
            band_means[b_name] = 0.0
            band_stats[b_name] = {
                "band_name": band_info[b_name]["name"],
                "wavelength_microns": band_info[b_name]["wavelength"],
                "mean_reflectance": 0.0,
                "stddev": 0.0,
                "min": 0.0,
                "max": 0.0
            }

    valid_count = ndwi_accum["count"]

    if valid_count > 0:
        mean_ndvi = ndvi_accum["sum"] / valid_count
        mean_ndwi = ndwi_accum["sum"] / valid_count
        mean_sr = (sr_accum["sum"] / valid_count) if valid_count > 0 else 0.0
        water_fraction = (ndwi_accum["gt_0"] / valid_count) * 100.0
        veg_fraction = (ndvi_accum["gt_02"] / valid_count) * 100.0
    else:
        mean_ndvi = 0.0
        mean_ndwi = 0.0
        mean_sr = 0.0
        water_fraction = 0.0
        veg_fraction = 0.0

    return {
        "band_stats": band_stats,
        "band_means": band_means,
        "mean_ndvi": mean_ndvi,
        "mean_ndwi": mean_ndwi,
        "mean_sr": mean_sr,
        "water_fraction": water_fraction,
        "veg_fraction": veg_fraction,
        "valid_count": valid_count,
        "crs": crs_str,
        "dimensions": {"width": width, "height": height}
    }


def run_spectral_analysis(
    upload_dir: Path = Path("uploads"),
    output_dir: Path = Path("uploads/multispectral"),
    size: int = 1024,
    target_scene: str = None,
    **kwargs
) -> dict:
    """
    Execute multispectral band reflectance analysis across B2, B3, B4, and B5.
    Calculates full-resolution per-band statistics and spectral indices (NDVI, NDWI, SR)
    using chunked streaming windows (1024x1024) to guarantee < 512 MB memory usage.
    """
    try:
        found_data = find_landsat_bands(upload_dir, target_scene=target_scene)
        if not found_data["found"]:
            return {
                "success": False,
                "tool": "spectral_band_analysis",
                "error": found_data.get("reason", "Could not locate matching Landsat B2-B5 bands.")
            }

        scene = found_data["scene"]
        bands = found_data["bands"]

        # Detect sensor identity and band wavelengths dynamically
        sensor_title, band_info = get_sensor_band_info(scene)

        # Compute full-resolution chunked statistics across B2, B3, B4, B5
        chunked = compute_chunked_spectral_statistics(bands, band_info, chunk_size=1024)

        if chunked["valid_count"] == 0:
            return {
                "success": False,
                "tool": "spectral_band_analysis",
                "error": "No valid surface reflectance pixels found across the 4 bands."
            }

        band_stats = chunked["band_stats"]
        band_means = chunked["band_means"]
        mean_ndvi = chunked["mean_ndvi"]
        mean_ndwi = chunked["mean_ndwi"]
        mean_sr = chunked["mean_sr"]
        water_fraction = chunked["water_fraction"]
        veg_fraction = chunked["veg_fraction"]

        # Environmental Signature Inference
        if mean_ndwi > 0.0:
            signature_type = "Water Body / High Moisture Dominant"
        elif mean_ndvi >= 0.40:
            signature_type = "Vigorous Green Vegetation Canopy"
        elif mean_ndvi >= 0.20:
            signature_type = "Moderate Vegetation (Grassland / Agricultural Cropland)"
        else:
            signature_type = "Sparse Vegetation / Bare Soil / Rock Surface"

        # Generate Spectral Profile Visualization Chart
        chart_filename = f"{scene}_spectral_profile.png"
        chart_path = output_dir / chart_filename
        draw_spectral_profile_chart(
            scene_name=scene,
            band_means=band_means,
            ndwi_val=mean_ndwi,
            ndvi_val=mean_ndvi,
            output_path=chart_path
        )

        # Mirror chart to uploads/multispectral/ to guarantee accessibility
        mirror_dir = Path("uploads") / "multispectral"
        mirror_dir.mkdir(parents=True, exist_ok=True)
        try:
            target_chart = mirror_dir / chart_filename
            if chart_path.resolve() != target_chart.resolve():
                shutil.copy2(chart_path, target_chart)
        except Exception:
            pass

        chart_web_url = to_web_url(chart_path)

        # Calculate ratio of mean bands as an internal consistency check
        mean_b3 = band_means.get("B3", 0.0)
        mean_b5 = band_means.get("B5", 0.0)
        ndwi_from_mean_bands = (mean_b3 - mean_b5) / (mean_b3 + mean_b5 + 1e-6)

        return {
            "success": True,
            "tool": "spectral_band_analysis",
            "operation": "NDWI",
            "scene": scene,
            "sensor": sensor_title,
            "bands_analyzed": list(band_stats.keys()),
            "band_statistics": band_stats,
            "spectral_indices": {
                "mean_ndvi": round(mean_ndvi, 4),
                "mean_ndwi_mcfeeters_1996": round(mean_ndwi, 4),
                "mean_pixel_ndwi": round(mean_ndwi, 4),
                "mean_ndwi": round(mean_ndwi, 4),
                "mean_b3_green_reflectance": round(mean_b3, 4),
                "mean_b5_nir_reflectance": round(mean_b5, 4),
                "ndwi_from_mean_bands": round(ndwi_from_mean_bands, 4),
                "expected_ndwi_from_displayed_values": round(ndwi_from_mean_bands, 4),
                "internal_consistency_audit": {
                    "mean_b3_reflectance": round(mean_b3, 4),
                    "mean_b5_reflectance": round(mean_b5, 4),
                    "mean_pixel_level_ndwi": round(mean_ndwi, 4),
                    "ratio_of_mean_bands": round(ndwi_from_mean_bands, 4),
                    "jensens_inequality_explanation": (
                        "Mean pixel-level NDWI represents the true spatial expectation across all valid pixels. "
                        "Because NDWI is a nonlinear ratio (Green-NIR)/(Green+NIR), E[(B3-B5)/(B3+B5)] != (E[B3]-E[B5])/(E[B3]+E[B5]) "
                        "when a scene contains distinct water (high NDWI, low NIR) and land (negative NDWI, high NIR) regimes."
                    )
                },
                "ndwi_formulation": "McFeeters (1996) Open Water Delineation: (Green - NIR) / (Green + NIR)",
                "simple_ratio_nir_red": round(mean_sr, 4),
                "vegetation_pixel_coverage_pct": round(veg_fraction, 2),
                "water_pixel_coverage_pct": round(water_fraction, 2)
            },
            "provenance": {
                "optical_scene": scene,
                "sensor": sensor_title,
                "scaling": "USGS Landsat Collection 2 Level-2 SR: DN * 0.0000275 - 0.2",
                "bands": {
                    "B2": str(bands.get("B2")),
                    "B3": str(bands.get("B3")),
                    "B4": str(bands.get("B4")),
                    "B5": str(bands.get("B5"))
                },
                "formulas": {
                    "NDWI": "McFeeters (1996): (Green [B3] - NIR [B5]) / (Green [B3] + NIR [B5])",
                    "NDVI": "Rouse (1974): (NIR [B5] - Red [B4]) / (NIR [B5] + Red [B4])",
                    "SimpleRatio": "NIR [B5] / Red [B4]"
                },
                "thresholds": {
                    "water_delineation": "NDWI > 0.0",
                    "vegetation_coverage": "NDVI >= 0.20"
                }
            },
            "spectral_signature_classification": signature_type,
            "evidence": {
                "spectral_profile_chart": chart_web_url,
                "chart_disk_path": str(chart_path),
                "artifact_type": "spectral_profile_chart",
                "filename": chart_filename,
                "url": chart_web_url
            },
            "processing_metadata": {
                "crs": chunked.get("crs"),
                "sampled_resolution": "full_resolution_chunked_1024x1024",
                "valid_pixel_count": int(chunked.get("valid_count", 0))
            }
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "spectral_band_analysis",
            "error": str(e)
        }
