from pathlib import Path


def interpret_ndvi_result(analysis: dict, vlm_synthesis: dict | None = None):
    """
    Interpret the result of NDVI analysis, combining deterministic spectral
    raster calculations with multimodal VLM visual synthesis.
    """

    # Support both ndvi_statistics (from ndvi_analysis tool) and generic statistics key
    statistics = analysis.get("ndvi_statistics") or analysis.get("statistics") or {}

    mean_ndvi = statistics.get("mean_ndvi") if statistics.get("mean_ndvi") is not None else statistics.get("mean")
    stddev = statistics.get("stddev")

    if mean_ndvi is None:
        return {
            "success": False,
            "message": "NDVI statistics are not available."
        }

    if mean_ndvi >= 0.5:
        interpretation = (
            f"The scene shows a strong overall vegetation signal with high canopy density (Mean NDVI: {mean_ndvi:.2f})."
        )
        density_label = "dense vegetation"
    elif mean_ndvi >= 0.2:
        interpretation = (
            f"The scene shows a moderate overall vegetation signal corresponding to cropland or grassland (Mean NDVI: {mean_ndvi:.2f})."
        )
        density_label = "moderate vegetation"
    elif mean_ndvi >= 0:
        interpretation = (
            f"The scene shows a relatively low overall vegetation signal with sparse vegetation alongside bare soil or urban surfaces (Mean NDVI: {mean_ndvi:.2f})."
        )
        density_label = "sparse vegetation"
    else:
        interpretation = (
            f"The scene shows predominantly low or negative vegetation signal indicating water, clouds, or non-vegetated surfaces (Mean NDVI: {mean_ndvi:.2f})."
        )
        density_label = "non-vegetated / water"

    # Evidence-based confidence
    confidence = 0.70
    confidence_reasons = ["Mean NDVI computed mathematically from Landsat surface reflectance."]
    if analysis.get("evidence", {}).get("ndvi_map"):
        confidence += 0.15
        confidence_reasons.append("Spatial NDVI map generated as visual evidence.")
    if stddev is not None and stddev < 0.25:
        confidence += 0.10
        confidence_reasons.append("NDVI spatial distribution shows consistent variance.")

    # Incorporate Multimodal VLM visual context
    vlm_text = ""
    if vlm_synthesis and vlm_synthesis.get("success") and not vlm_synthesis.get("deployment_constrained") and vlm_synthesis.get("vlm_available", True):
        vlm_text = vlm_synthesis.get("answer", "").strip()
        if vlm_text:
            interpretation += f"\n\nMultimodal Visual Context:\n{vlm_text}"
            confidence = min(confidence + 0.05, 1.0)
            confidence_reasons.append("Multimodal VLM visual context synthesized with NDVI spectral statistics.")

    confidence = min(max(confidence, 0.0), 1.0)
    confidence_level = "high" if confidence >= 0.80 else ("medium" if confidence >= 0.60 else "low")

    return {
        "success": True,
        "interpretation": interpretation,
        "vegetation_category": density_label,
        "confidence": {
            "score": round(confidence, 2),
            "level": confidence_level,
            "basis": confidence_reasons
        },
        "basis": {
            "mean_ndvi": mean_ndvi,
            "stddev": stddev,
            "vlm_synthesis": vlm_text if vlm_text else None
        }
    }


def interpret_change_detection_result(analysis: dict, vlm_synthesis: dict | None = None):
    """
    Interpret NDVI change-detection results, incorporating spatial dynamics,
    3-panel comparative evidence, and multimodal Change-VQA synthesis.
    """

    statistics = analysis.get("statistics", {})

    baseline_mean = statistics.get("baseline_mean_ndvi") if statistics.get("baseline_mean_ndvi") is not None else statistics.get("before_mean_ndvi")
    monitoring_mean = statistics.get("monitoring_mean_ndvi") if statistics.get("monitoring_mean_ndvi") is not None else statistics.get("after_mean_ndvi")
    mean_change = statistics.get("mean_delta_ndvi") if statistics.get("mean_delta_ndvi") is not None else (statistics.get("delta_mean_ndvi") if statistics.get("delta_mean_ndvi") is not None else statistics.get("mean_ndvi_change"))
    stddev = statistics.get("stddev")
    increase_percentage = statistics.get("vegetation_gain_percentage") if statistics.get("vegetation_gain_percentage") is not None else statistics.get("increase_percentage")
    decrease_percentage = statistics.get("vegetation_loss_percentage") if statistics.get("vegetation_loss_percentage") is not None else statistics.get("decrease_percentage")
    stable_percentage = statistics.get("stable_percentage")

    if (
        mean_change is None
        or stddev is None
        or increase_percentage is None
        or decrease_percentage is None
        or stable_percentage is None
    ):
        return {
            "success": False,
            "message": "Change-detection statistics are incomplete."
        }

    # Dynamic classification & dates
    dynamic = statistics.get("dynamic_classification", "Bi-temporal Change Detected")
    before_date = analysis.get("before", {}).get("date", "Before Scene")
    after_date = analysis.get("after", {}).get("date", "After Scene")

    # --------------------------------------------------
    # Calculate confidence
    # --------------------------------------------------

    confidence = 0.60
    confidence_reasons = []

    if abs(mean_change) >= 0.02:
        confidence += 0.10
        confidence_reasons.append("Mean NDVI difference indicates measurable temporal change.")
    else:
        confidence_reasons.append("Mean NDVI difference shows minor net overall variance.")

    if stddev < 0.30:
        confidence += 0.10
        confidence_reasons.append("NDVI delta variance remains within controlled physical thresholds.")

    evidence = analysis.get("evidence", {})
    if evidence.get("change_map"):
        confidence += 0.10
        confidence_reasons.append("Spatial NDVI difference heatmap generated as visual evidence.")

    if evidence.get("comparison_triplet"):
        confidence += 0.05
        confidence_reasons.append("3-panel Before/After/Change comparative triplet generated as visual evidence.")

    # --------------------------------------------------
    # Human-readable interpretation & Change-VQA
    # --------------------------------------------------

    baseline_lines = ""
    if baseline_mean is not None and monitoring_mean is not None:
        baseline_lines = (
            f"• Baseline Mean NDVI (T1): {baseline_mean:.4f}\n"
            f"• Monitoring Mean NDVI (T2): {monitoring_mean:.4f}\n"
        )

    interpretation = (
        f"Bi-temporal satellite change detection between {before_date} and {after_date}:\n"
        f"{baseline_lines}"
        f"• Dynamic Pattern: {dynamic}\n"
        f"• Mean NDVI Shift: {mean_change:+.4f}\n"
        f"• Vegetation Gain: {increase_percentage:.1f}% (green pixels)\n"
        f"• Vegetation Loss: {decrease_percentage:.1f}% (red pixels)\n"
        f"• Stable Terrain: {stable_percentage:.1f}% (gray pixels)"
    )

    vlm_text = ""
    if vlm_synthesis and vlm_synthesis.get("success") and not vlm_synthesis.get("deployment_constrained") and vlm_synthesis.get("vlm_available", True):
        vlm_text = vlm_synthesis.get("answer", "").strip()
        if vlm_text:
            interpretation += f"\n\nChange-VQA Multimodal Synthesis:\n{vlm_text}"
            confidence = min(confidence + 0.05, 1.0)
            confidence_reasons.append("Multimodal VLM visual synthesis integrated with bi-temporal delta metrics.")

    confidence = min(max(confidence, 0.0), 1.0)
    confidence_level = "high" if confidence >= 0.80 else ("medium" if confidence >= 0.60 else "low")

    return {
        "success": True,
        "interpretation": interpretation,
        "dynamic_classification": dynamic,
        "confidence": {
            "score": round(confidence, 2),
            "level": confidence_level,
            "basis": confidence_reasons
        },
        "basis": {
            "before_date": before_date,
            "after_date": after_date,
            "baseline_mean_ndvi": baseline_mean,
            "monitoring_mean_ndvi": monitoring_mean,
            "before_mean_ndvi": baseline_mean,
            "after_mean_ndvi": monitoring_mean,
            "mean_delta_ndvi": mean_change,
            "delta_mean_ndvi": mean_change,
            "mean_ndvi_change": mean_change,
            "stddev": stddev,
            "vegetation_gain_percentage": increase_percentage,
            "increase_percentage": increase_percentage,
            "vegetation_loss_percentage": decrease_percentage,
            "decrease_percentage": decrease_percentage,
            "stable_percentage": stable_percentage,
            "dynamic_classification": dynamic,
            "comparison_triplet": evidence.get("comparison_triplet"),
            "change_map": evidence.get("change_map"),
            "vlm_synthesis": vlm_text if vlm_text else None
        }
    }


def interpret_vlm_result(analysis: dict):
    """
    Interpret the response from the Remote Sensing Vision-Language Model.
    """
    answer = analysis.get("answer", "")
    image_analyzed = analysis.get("image_analyzed", "")
    model_metadata = analysis.get("model_metadata", {})

    if analysis.get("deployment_constrained"):
        return {
            "success": True,
            "interpretation": answer,
            "headline": "VLM Offline (Cloud Deployment Memory Constraint)",
            "summary": answer,
            "confidence": {
                "score": 0.85,
                "level": "high",
                "explanation": "Estimated from deterministic calculations, generated evidence and spatial consistency.",
                "deployment_constrained": True,
                "basis": [
                    "Host environment enforces 512 MB memory limit (Render Free Tier).",
                    "SmolVLM-500M inference requires ~1.66 GB RAM and was bypassed to preserve uptime.",
                    "Deterministic scientific engines (NDVI, NDWI, Change Detection, Radar Fusion) are active."
                ]
            },
            "basis": {
                "status": "deployment_constrained",
                "vlm_available": False,
                "required_ram_mb": 1700,
                "available_host_limit_mb": 512
            }
        }

    if not answer:
        return {
            "success": False,
            "message": "No answer was returned by the VLM."
        }

    # Evidence-based confidence
    confidence = 0.85
    confidence_reasons = [
        "Analysis performed using fine-tuned SmolVLM-500M remote-sensing LoRA model."
    ]

    if image_analyzed:
        confidence_reasons.append(
            f"Visual features grounded from image: {Path(image_analyzed).name}"
        )
        confidence += 0.05

    if model_metadata.get("adapter_active"):
        confidence_reasons.append(
            f"Domain-adapted PEFT adapter active ({model_metadata.get('adapter_path')})."
        )

    confidence = min(max(confidence, 0.0), 1.0)
    confidence_level = "high" if confidence >= 0.80 else "medium"

    return {
        "success": True,
        "interpretation": answer,
        "confidence": {
            "score": round(confidence, 2),
            "level": confidence_level,
            "basis": confidence_reasons
        },
        "basis": {
            "image_analyzed": image_analyzed,
            "raw_answer": answer,
            "latency_seconds": model_metadata.get("latency_seconds"),
            "adapter_active": model_metadata.get("adapter_active"),
            "device": model_metadata.get("device")
        }
    }


def interpret_spectral_result(analysis: dict, vlm_synthesis: dict | None = None):
    """
    Interpret the results of multispectral band analysis and spectral profile signature.
    """
    if not analysis.get("success"):
        return {
            "success": False,
            "message": analysis.get("error", "Spectral band analysis failed.")
        }

    bands = analysis.get("band_statistics", {})
    indices = analysis.get("spectral_indices", {})
    scene = analysis.get("scene", "")
    sig_type = analysis.get("spectral_signature_classification", "Unclassified Surface")

    mean_ndvi = indices.get("mean_ndvi", 0.0)
    mean_ndwi = indices.get("mean_ndwi", 0.0)
    sr = indices.get("simple_ratio_nir_red", 0.0)
    veg_cov = indices.get("vegetation_pixel_coverage_pct", 0.0)
    water_cov = indices.get("water_pixel_coverage_pct", 0.0)

    b2 = bands.get("B2", {}).get("mean_reflectance", 0.0)
    b3 = bands.get("B3", {}).get("mean_reflectance", 0.0)
    b4 = bands.get("B4", {}).get("mean_reflectance", 0.0)
    b5 = bands.get("B5", {}).get("mean_reflectance", 0.0)
    ndwi_of_means = indices.get("ndwi_from_mean_bands", (b3 - b5) / (b3 + b5 + 1e-6))

    interpretation = (
        f"Multispectral signature extracted across 4 Landsat optical bands for scene {scene}:\n"
        f"• Blue (0.48µm): {b2:.3f} | Green (0.56µm): {b3:.3f} | Red (0.65µm): {b4:.3f} | NIR (0.86µm): {b5:.3f}\n"
        f"• Mean B3 Green Reflectance: {b3:.3f}\n"
        f"• Mean B5 NIR Reflectance: {b5:.3f}\n"
        f"• Environmental Signature: {sig_type}\n"
        f"• Mean NDVI (Vegetation): {mean_ndvi:+.3f} ({veg_cov:.1f}% vegetative pixel coverage at threshold >= 0.20)\n"
        f"• Mean Pixel-Level NDWI (McFeeters 1996 Open Water): {mean_ndwi:+.3f} ({water_cov:.1f}% water/high-moisture coverage at threshold > 0.0)\n"
        f"• Simple Biomass Ratio (NIR/Red): {sr:.2f}\n"
        f"• Mathematical Note: Mean pixel-level NDWI ({mean_ndwi:+.3f}) is computed directly from aligned pixel arrays. "
        f"Because NDWI is a nonlinear ratio, the pixel-level spatial mean naturally differs from the ratio of scene-wide mean band reflectances ({ndwi_of_means:+.3f})."
    )

    confidence = 0.85
    confidence_reasons = [
        "Surface reflectance calibrated from 4 physical Landsat-8/9 optical bands (B2, B3, B4, B5).",
        "Deterministic NDVI and NDWI spectral indices computed directly from calibrated band arrays."
    ]

    if analysis.get("evidence", {}).get("spectral_profile_chart"):
        confidence += 0.05
        confidence_reasons.append("Spectral profile reflectance chart generated as visual evidence.")

    vlm_text = ""
    if vlm_synthesis and vlm_synthesis.get("success") and not vlm_synthesis.get("deployment_constrained") and vlm_synthesis.get("vlm_available", True):
        vlm_text = vlm_synthesis.get("answer", "").strip()
        if vlm_text:
            interpretation += f"\n\nMultimodal Visual Context:\n{vlm_text}"
            confidence = min(confidence + 0.05, 1.0)
            confidence_reasons.append("Multimodal VLM visual context synthesized with spectral band data.")

    confidence = min(max(confidence, 0.0), 1.0)
    confidence_level = "high" if confidence >= 0.80 else "medium"

    return {
        "success": True,
        "interpretation": interpretation,
        "signature_type": sig_type,
        "confidence": {
            "score": round(confidence, 2),
            "level": confidence_level,
            "basis": confidence_reasons
        },
        "basis": {
            "scene": scene,
            "bands": bands,
            "spectral_indices": indices,
            "spectral_profile_chart": analysis.get("evidence", {}).get("spectral_profile_chart"),
            "vlm_synthesis": vlm_text if vlm_text else None
        }
    }


def interpret_optical_sar_result(analysis: dict, vlm_synthesis: dict | None = None) -> dict:
    """
    Interpret multimodal Optical + SAR fusion results, combining optical spectral indices
    with active microwave SAR polarimetric backscatter and cross-sensor consensus.
    """
    if not analysis.get("success"):
        return {
            "success": False,
            "message": analysis.get("error", "Optical + SAR fusion analysis failed.")
        }

    opt_metrics = analysis.get("optical_metrics", {})
    sar_metrics = analysis.get("sar_metrics", {})
    fusion_metrics = analysis.get("fusion_metrics", {})
    evidence = analysis.get("evidence", {})

    opt_scene = analysis.get("optical_scene", "Optical Scene")
    sar_scene = analysis.get("sar_scene", "SAR Scene")

    mean_ndvi = opt_metrics.get("mean_ndvi", 0.0)
    mean_ndwi = opt_metrics.get("mean_ndwi", 0.0)
    veg_cov = opt_metrics.get("vegetation_pixel_coverage_pct", opt_metrics.get("vegetation_coverage_pct", 0.0))
    opt_water = opt_metrics.get("potential_water_coverage_pct", opt_metrics.get("water_coverage_pct", 0.0))

    vv_db = sar_metrics.get("mean_sigma0_vv_db", 0.0)
    vh_db = sar_metrics.get("mean_sigma0_vh_db", 0.0)
    rvi = sar_metrics.get("mean_rvi", 0.0)
    vh_vv_ratio = sar_metrics.get("cross_polarization_ratio_db", 0.0)
    sar_water = sar_metrics.get("sar_specular_water_coverage_pct", 0.0)
    urban_cov = sar_metrics.get("urban_roughness_coverage_pct", 0.0)

    classification = fusion_metrics.get("environmental_classification", "Multimodal Fusion Scene")
    agreement_score = fusion_metrics.get("prototype_cross_sensor_agreement_score", fusion_metrics.get("cross_sensor_vegetation_agreement_pct", 0.0))
    fused_water_pct = fusion_metrics.get("potential_water_inundation_coverage_pct", fusion_metrics.get("all_weather_water_coverage_pct", 0.0))
    corr = fusion_metrics.get("optical_sar_correlation")
    corr_str = f"r = {corr:+.2f}" if corr is not None else "Insufficient aligned pixels for correlation"

    interpretation = (
        f"Multimodal Optical + SAR Fusion Analysis:\n"
        f"• Combined Sensors: Landsat Optical ({opt_scene[:24]}) + Sentinel-1 C-SAR ({sar_scene[:24]})\n"
        f"• Environmental Classification: {classification}\n"
        f"• Optical Signals: Mean NDVI = {mean_ndvi:+.3f} (Vegetation pixel coverage: {veg_cov:.1f}% at threshold NDVI >= 0.20), Mean NDWI = {mean_ndwi:+.3f}\n"
        f"• Active Radar Polarimetry: Mean VV = {vv_db:.2f} dB, Mean VH = {vh_db:.2f} dB, Radar Veg Index (RVI) = {rvi:.3f} (linear domain: 4*VH/(VV+VH))\n"
        f"• Cross-Polarization Ratio (VH - VV): {vh_vv_ratio:+.2f} dB (canopy volume scattering vs. surface roughness)\n"
        f"• Potential Water / Inundation Signal: {fused_water_pct:.1f}% (prototype thresholds: optical NDWI > 0.0 OR SAR specular reflection VV < -18 dB)\n"
        f"• Prototype Cross-Sensor Agreement: {agreement_score:.1f}% spatial agreement score between optical vigor and radar structural scattering ({corr_str})"
    )

    confidence = 0.85
    confidence_reasons = [
        "Calibrated surface reflectance from physical Landsat-9 optical bands.",
        "Calibrated sigma-naught (dB) backscatter from Sentinel-1 active C-band SAR.",
        f"Dual-sensor cross-validation achieved {agreement_score:.1f}% spatial agreement."
    ]

    if evidence.get("fusion_composite"):
        confidence += 0.05
        confidence_reasons.append("4-panel multimodal fusion composite generated as visual evidence.")

    vlm_text = ""
    if vlm_synthesis and vlm_synthesis.get("success") and not vlm_synthesis.get("deployment_constrained") and vlm_synthesis.get("vlm_available", True):
        vlm_text = vlm_synthesis.get("answer", "").strip()
        if vlm_text:
            interpretation += f"\n\nMultimodal Visual Context & Scientific Insights:\n{vlm_text}"
            confidence = min(confidence + 0.05, 1.0)
            confidence_reasons.append("Multimodal VLM visual context synthesized with fused optical and polarimetric radar metrics.")

    confidence = min(max(confidence, 0.0), 1.0)
    confidence_level = "high" if confidence >= 0.80 else "medium"

    return {
        "success": True,
        "interpretation": interpretation,
        "classification": classification,
        "confidence": {
            "score": round(confidence, 2),
            "level": confidence_level,
            "basis": confidence_reasons
        },
        "basis": {
            "optical_scene": opt_scene,
            "sar_scene": sar_scene,
            "optical_metrics": opt_metrics,
            "sar_metrics": sar_metrics,
            "fusion_metrics": fusion_metrics,
            "fusion_composite": evidence.get("fusion_composite"),
            "vlm_synthesis": vlm_text if vlm_text else None
        }
    }


def interpret_metadata_result(analysis: dict) -> dict:
    """
    Interpret deterministic scene metadata retrieval results.
    """
    if not analysis.get("success"):
        return {
            "success": False,
            "message": analysis.get("error", "Failed to retrieve scene metadata.")
        }
    meta = analysis.get("metadata", {})
    scene_id = analysis.get("scene_id", "Selected Scene")
    interpretation = (
        f"Authoritative Scene Metadata ({scene_id}):\n"
        f"• Satellite / Platform: {meta.get('satellite', 'Not available')}\n"
        f"• Sensor Instrument: {meta.get('sensor', 'Not available')}\n"
        f"• Acquisition Date: {meta.get('acquisition_date', 'Not available')}\n"
        f"• Spatial Resolution: {meta.get('spatial_resolution', 'Not available')}\n"
        f"• Coordinate Reference System (CRS): {meta.get('crs', 'Not available')}\n"
        f"• WRS-2 Path/Row: {meta.get('path_row', 'Not available')}\n"
        f"• Available Bands: {', '.join(meta.get('bands', [])) if meta.get('bands') else 'Standard RGB'}"
    )
    return {
        "success": True,
        "interpretation": interpretation,
        "confidence": {
            "score": 1.0,
            "level": "high",
            "basis": ["Deterministic metadata retrieved directly from verified scene catalog."]
        },
        "basis": {
            "scene_id": scene_id,
            "metadata": meta
        }
    }


def interpret_unsupported_result(analysis: dict) -> dict:
    """
    Interpret unsupported capability responses (e.g. weather forecasting).
    """
    msg = analysis.get("message", "This capability is not supported by SatQuery AI.")
    return {
        "success": True,
        "interpretation": msg,
        "confidence": {
            "score": 1.0,
            "level": "high",
            "basis": ["Operational capability boundary enforcement."]
        },
        "basis": {
            "supported": False
        }
    }