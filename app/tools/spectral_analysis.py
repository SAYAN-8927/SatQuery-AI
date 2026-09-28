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


def run_spectral_analysis(
    upload_dir: Path = Path("uploads"),
    output_dir: Path = Path("uploads/multispectral"),
    size: int = 1024,
    target_scene: str = None,
    **kwargs
) -> dict:
    """
    Execute multispectral band reflectance analysis across B2, B3, B4, and B5.
    Calculates per-band statistics, spectral indices (NDVI, NDWI, SR),
    and generates a professional spectral signature profile chart.
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

        # Read bands
        b2_raw, p2 = read_band(bands["B2"], size)
        b3_raw, p3 = read_band(bands["B3"], size)
        b4_raw, p4 = read_band(bands["B4"], size)
        b5_raw, p5 = read_band(bands["B5"], size)

        # Scale to surface reflectance
        b2 = scale_landsat_surface_reflectance(b2_raw, p2["nodata"])
        b3 = scale_landsat_surface_reflectance(b3_raw, p3["nodata"])
        b4 = scale_landsat_surface_reflectance(b4_raw, p4["nodata"])
        b5 = scale_landsat_surface_reflectance(b5_raw, p5["nodata"])

        # Create valid mask
        valid_mask = (
            np.isfinite(b2)
            & np.isfinite(b3)
            & np.isfinite(b4)
            & np.isfinite(b5)
            & (b2 >= 0)
            & (b3 >= 0)
            & (b4 >= 0)
            & (b5 >= 0)
        )

        if not np.any(valid_mask):
            return {
                "success": False,
                "tool": "spectral_band_analysis",
                "error": "No valid surface reflectance pixels found across the 4 bands."
            }

        # Detect sensor identity and band wavelengths dynamically
        sensor_title, band_info = get_sensor_band_info(scene)

        # Calculate per-band reflectance statistics
        band_stats = {}
        band_means = {}
        raw_bands = {"B2": b2, "B3": b3, "B4": b4, "B5": b5}

        for b_name, b_arr in raw_bands.items():
            vals = b_arr[valid_mask]
            mean_v = float(np.mean(vals))
            std_v = float(np.std(vals))
            min_v = float(np.min(vals))
            max_v = float(np.max(vals))

            band_means[b_name] = mean_v
            band_stats[b_name] = {
                "band_name": band_info[b_name]["name"],
                "wavelength_microns": band_info[b_name]["wavelength"],
                "mean_reflectance": round(mean_v, 4),
                "stddev": round(std_v, 4),
                "min": round(min_v, 4),
                "max": round(max_v, 4)
            }

        # Calculate Spectral Indices
        v_b3 = b3[valid_mask]
        v_b4 = b4[valid_mask]
        v_b5 = b5[valid_mask]

        # NDVI = (NIR - Red) / (NIR + Red)
        ndvi_arr = (v_b5 - v_b4) / (v_b5 + v_b4 + 1e-6)
        mean_ndvi = float(np.mean(ndvi_arr))

        # NDWI (McFeeters 1996) = (Green - NIR) / (Green + NIR)
        # Specifically formulated for open water body and surface moisture delineation
        ndwi_arr = (v_b3 - v_b5) / (v_b3 + v_b5 + 1e-6)
        mean_ndwi = float(np.mean(ndwi_arr))

        # Simple Ratio = NIR / Red
        sr_arr = v_b5 / (v_b4 + 1e-6)
        mean_sr = float(np.mean(sr_arr))

        water_fraction = float(np.mean(ndwi_arr > 0.0) * 100.0)
        veg_fraction = float(np.mean(ndvi_arr > 0.20) * 100.0)

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
                "crs": p2.get("crs"),
                "sampled_resolution": f"{size}x{size}",
                "valid_pixel_count": int(np.sum(valid_mask))
            }
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "spectral_band_analysis",
            "error": str(e)
        }
