import re

INTENT_SPECS = {
    "vegetation_analysis": {
        "tool": "ndvi_analysis",
        "description": "Vegetation index (NDVI) computation and canopy density analysis",
        "quantitative": True,
        "required_modalities": ["optical"],
        "required_bands": ["red", "nir"],
        "required_scene_count": 1,
        "temporal_requirement": False
    },
    "water_analysis": {
        "tool": "spectral_band_analysis",
        "operation": "NDWI",
        "description": "Normalized Difference Water Index (NDWI) water delineation and surface moisture analysis",
        "quantitative": True,
        "required_modalities": ["optical"],
        "required_bands": ["b3", "b5"],
        "required_scene_count": 1,
        "temporal_requirement": False
    },
    "spectral_analysis": {
        "tool": "spectral_band_analysis",
        "operation": "spectral_profile",
        "description": "Multispectral band statistics (B2-B5) and water delineation (NDWI)",
        "quantitative": True,
        "required_modalities": ["optical"],
        "required_bands": ["b2", "b3", "b4", "b5"],
        "required_scene_count": 1,
        "temporal_requirement": False
    },
    "change_detection": {
        "tool": "change_detection_model",
        "description": "Bi-temporal change detection and vegetation dynamics between acquisition dates",
        "quantitative": True,
        "required_modalities": ["optical"],
        "required_bands": ["red", "nir"],
        "required_scene_count": 2,
        "temporal_requirement": True
    },
    "optical_sar_analysis": {
        "tool": "optical_sar_model",
        "description": "Multimodal cross-sensor fusion combining optical reflectance with Sentinel-1 SAR polarimetric radar",
        "quantitative": True,
        "required_modalities": ["optical", "sar"],
        "required_bands": ["optical_rgb", "sar_vv", "sar_vh"],
        "required_scene_count": "1 optical + 1 compatible SAR",
        "temporal_requirement": False
    },
    "scene_metadata_retrieval": {
        "tool": "scene_metadata_model",
        "description": "Deterministic retrieval of verified satellite, sensor, acquisition date, and spatial resolution metadata",
        "quantitative": True,
        "required_modalities": ["optical", "sar"],
        "required_bands": [],
        "required_scene_count": 1,
        "temporal_requirement": False
    },
    "unsupported_capability": {
        "tool": "unsupported_capability_handler",
        "description": "Capability-aware response for requests outside Earth observation scope (e.g. weather forecasting)",
        "quantitative": False,
        "required_modalities": [],
        "required_bands": [],
        "required_scene_count": 0,
        "temporal_requirement": False
    },
    "scene_description": {
        "tool": "remote_sensing_vlm",
        "description": "Visual scene inspection, object/feature recognition, and VQA via Vision-Language Model",
        "quantitative": False,
        "required_modalities": ["optical"],
        "required_bands": [],
        "required_scene_count": 1,
        "temporal_requirement": False
    }
}


def parse_query(query: str):
    """
    Semantic Multi-Intent Natural Query Parser for SatQuery AI.

    Decomposes natural language queries into one or more structured operational intents:
      - multi_intent: True if multiple distinct operations were requested
      - intent: Primary operational intent (backward compatible)
      - intents: List of all detected intent dictionaries in order of request
      - primary_intent: The primary operational intent name
      - secondary_intents: List of secondary intent names
      - required_modalities: Aggregated modalities (optical, sar)
      - temporal_requirement: True if any intent requires temporal comparison
      - required_bands: Union of required bands
      - required_scene_count: Maximum required scene count
    """
    raw_query = query
    query_str = (query or "").lower().strip()

    if not query_str:
        return {
            "success": False,
            "multi_intent": False,
            "intent": "unknown",
            "tool": None,
            "primary_intent": "unknown",
            "secondary_intents": [],
            "intents": [],
            "confidence": 0.0,
            "reason": "Query cannot be empty.",
            "required_modalities": ["optical"],
            "temporal_requirement": False,
            "required_bands": [],
            "required_scene_count": 1,
            "matched_keywords": [],
            "concepts_detected": []
        }

    detected_intents = []
    all_matched_keywords = []
    concepts_detected = []

    # Helper for token matching
    def has_any(terms):
        matches = []
        for t in terms:
            idx = query_str.find(t)
            if idx != -1:
                matches.append((idx, t))
        return matches

    # --------------------------------------------------
    # 0. UNSUPPORTED CAPABILITIES (Weather, Tomorrow, etc.)
    # --------------------------------------------------
    unsupported_terms = [
        "weather", "forecast", "tomorrow", "meteorology", "rain tomorrow",
        "temperature tomorrow", "stock market", "crypto", "bitcoin", "horoscope"
    ]
    matched_unsupported = has_any(unsupported_terms)
    if matched_unsupported:
        first_pos = min(m[0] for m in matched_unsupported)
        kws = [m[1] for m in matched_unsupported]
        spec = INTENT_SPECS["unsupported_capability"].copy()
        spec["intent"] = "unsupported_capability"
        spec["confidence"] = 1.0
        spec["reason"] = "Query requests an unsupported capability (such as weather forecasting or future prediction)."
        spec["matched_keywords"] = kws
        detected_intents.append((first_pos, spec))
        concepts_detected.append("unsupported_capability")
        all_matched_keywords.extend(kws)

    # --------------------------------------------------
    # 1. SCENE METADATA RETRIEVAL (Deterministic)
    # --------------------------------------------------
    metadata_patterns = [
        "satellite/sensor", "satellite and sensor", "satellite or sensor",
        "what satellite", "which satellite", "what sensor", "which sensor",
        "acquisition date", "date of acquisition", "when was this acquired",
        "spatial resolution", "what resolution", "ground sampling distance",
        "coordinate reference system", "what crs", "which crs", "projection",
        "path and row", "path/row", "wrs-2", "metadata are associated",
        "metadata associated", "metadata of this", "metadata for this",
        "satellite, sensor, acquisition date", "sensor and acquisition date"
    ]
    matched_metadata = has_any(metadata_patterns)
    has_meta_compound = (
        ("satellite" in query_str or "sensor" in query_str)
        and ("acquisition date" in query_str or "date" in query_str)
        and ("resolution" in query_str or "spatial" in query_str)
    )
    if matched_metadata or has_meta_compound:
        first_pos = min(m[0] for m in matched_metadata) if matched_metadata else query_str.find("satellite")
        kws = [m[1] for m in matched_metadata] if matched_metadata else ["satellite", "sensor", "date", "resolution"]
        spec = INTENT_SPECS["scene_metadata_retrieval"].copy()
        spec["intent"] = "scene_metadata_retrieval"
        spec["confidence"] = 0.98
        spec["reason"] = "Observation metadata (satellite, sensor, acquisition date, resolution) requested deterministically."
        spec["matched_keywords"] = kws
        detected_intents.append((first_pos, spec))
        concepts_detected.append("scene_metadata_retrieval")
        all_matched_keywords.extend(kws)

    # --------------------------------------------------
    # 2. OPTICAL + SAR MULTIMODAL CONCEPTS
    # --------------------------------------------------
    # --------------------------------------------------
    # 2. OPTICAL + SAR MULTIMODAL CONCEPTS
    # --------------------------------------------------
    joint_optical_sar_patterns = [
        "optical and sar", "optical vs sar", "optical-sar", "optical + sar",
        "sar and optical", "sar vs optical", "sar + optical", "radar and optical",
        "optical and radar", "optical + radar", "radar + optical", "fuse optical and sar",
        "fuse optical and radar", "optical and microwave", "reflected-light",
        "reflected light", "radar perspective", "radar observation", "sar perspective",
        "sar observation", "sar fusion", "multimodal fusion", "cross-sensor fusion",
        "radar vegetation index", "polarimetric radar",
        "optical and radar information", "optical and sar information",
        "combine optical and sar", "combine optical and radar",
        "combine the multispectral and radar", "combine multispectral and radar",
        "combined optical and sar", "combined optical and radar", "combined optical-radar",
        "combined interpretation using reflected light and radar",
        "reflected light and radar", "reflected light and sar",
        "satellite image and radar", "satellite and radar",
        "multispectral and radar", "multispectral and sar",
        "use both sensors", "using both sensors",
        "use both the optical and radar", "use both optical and radar",
        "use both optical and sar", "both the optical and radar",
        "both optical and radar", "both the optical and sar", "both optical and sar",
        "compare the optical and sar", "compare the optical and radar",
        "compare optical and sar", "compare optical and radar",
        "optical and radar information to analyze", "use both observations"
    ]
    matched_joint_sar = has_any(joint_optical_sar_patterns)
    has_optical_ref = any(k in query_str for k in ["optical", "reflected-light", "reflected light", "visible light", "multispectral"])
    has_radar_ref = any(k in query_str for k in ["sar", "radar", "sentinel-1", "backscatter", "polarimetric", "microwave"])
    has_optical_sar = bool(matched_joint_sar or (has_optical_ref and has_radar_ref) or ("both sensors" in query_str) or ("both observations" in query_str and (has_optical_ref or has_radar_ref)))

    if has_optical_sar:
        first_pos = min(m[0] for m in matched_joint_sar) if matched_joint_sar else min(query_str.find(k) for k in ["optical", "radar", "sar", "sensor", "observation"] if query_str.find(k) != -1)
        kws = [m[1] for m in matched_joint_sar] if matched_joint_sar else [k for k in ["optical", "radar", "sar", "both sensors"] if k in query_str]
        spec = INTENT_SPECS["optical_sar_analysis"].copy()
        spec["intent"] = "optical_sar_analysis"
        spec["confidence"] = 0.96
        spec["reason"] = "Multimodal cross-sensor optical and Sentinel-1 SAR radar fusion requested."
        spec["matched_keywords"] = kws
        detected_intents.append((first_pos, spec))
        concepts_detected.append("optical_sar")
        all_matched_keywords.extend(kws)

    # --------------------------------------------------
    # 3. BI-TEMPORAL CHANGE DETECTION CONCEPTS
    # (Do not trigger false change detection if query is explicitly cross-modal Optical + SAR)
    # --------------------------------------------------
    temporal_comparison_patterns = [
        "between two dates", "between dates", "compare these two dates",
        "compare two dates", "compare the two dates", "compare dates",
        "earlier and later", "earlier vs later", "earlier observation",
        "later observation", "previous observation", "subsequent observation",
        "different from the previous observation", "different from previous observation",
        "different from the earlier observation", "two acquisitions", "both acquisitions",
        "between acquisitions", "before and after", "changes between", "change between", "across time",
        "over time", "time series", "bi-temporal", "bitemporal", "multi-temporal",
        "temporal change", "temporal comparison", "compare these two scenes",
        "compare two scenes", "compare both scenes",
        "shifted between", "pattern has shifted", "vegetation shift between",
        "vegetation has shifted", "increased, decreased, or remained relatively stable",
        "increased, decreased, or stable", "gain and loss", "gain or loss",
        "vegetation-related change", "vegetation change", "meaningful vegetation change",
        "what changed", "what has changed", "tell me what changed", "tell me the changes",
        "detect changes over time", "change over time", "changed here compared with another",
        "changed over time", "indicate vegetation has changed"
    ]
    if not has_optical_sar:
        temporal_comparison_patterns.extend([
            "two observations", "both observations",
            "contrast the two observations", "contrast the observations", "compare the two observations"
        ])
    matched_temporal = has_any(temporal_comparison_patterns)
    if matched_temporal and not has_optical_sar:
        first_pos = min(m[0] for m in matched_temporal)
        kws = [m[1] for m in matched_temporal]
        spec = INTENT_SPECS["change_detection"].copy()
        spec["intent"] = "change_detection"
        spec["confidence"] = 0.94
        spec["reason"] = "Bi-temporal change detection and landscape dynamics requested."
        spec["matched_keywords"] = kws
        detected_intents.append((first_pos, spec))
        concepts_detected.append("change_detection")
        all_matched_keywords.extend(kws)

    # --------------------------------------------------
    # 4. EXPLICIT VISUAL-ONLY OVERRIDE CHECK
    # --------------------------------------------------
    is_explicit_visual_only = any(
        phrase in query_str
        for phrase in [
            "forget spectral calculations", "forget spectral", "without spectral",
            "looking only at what can actually be seen", "looking only at what is visible",
            "only at what can actually be seen", "purely visual"
        ]
    ) and not any(neg in query_str for neg in ["don't need", "dont need", "do not need", "no visual guess"])

    # --------------------------------------------------
    # 5. VEGETATION QUANTIFICATION / ANALYSIS (NDVI)
    # --------------------------------------------------
    if not is_explicit_visual_only:
        ndvi_explicit_terms = [
            "calculate ndvi", "compute ndvi", "calculate vegetation", "compute vegetation",
            "vegetation index", "ndvi value", "mean ndvi", "canopy density calculation",
            "formula for ndvi", "ndvi formula", "calibrated ndvi", "ndvi",
            "derive the vegetation index", "normalized difference between",
            "normalized difference vegetation"
        ]
        has_red = any(r in query_str for r in ["red information", "red measurement", "red band", "b4", " red ", "red,"]) or query_str.startswith("red") or query_str.endswith("red")
        has_nir = any(n in query_str for n in ["near-infrared", "near infrared", "nir", "b5"])
        has_red_nir = (has_red and has_nir) or "red and near-infrared" in query_str or "near-infrared and red" in query_str or "red and nir" in query_str or "nir and red" in query_str

        vegetation_quant_terms = [
            "quantify vegetation", "quantifying vegetation", "quantify how healthy",
            "quantify its vegetation", "quantify how healthy the vegetation",
            "relative greenness", "how green is this landscape", "level of greenness",
            "canopy greenness", "greenness of the surface", "vegetation condition",
            "vegetation vigor", "vegetation health", "vegetation density", "canopy density",
            "how much vegetation is present", "amount of vegetation", "vegetation measurement",
            "multispectral vegetation measurement", "measure vegetation",
            "computed vegetation measurement", "derive the vegetation", "calculate the vegetation"
        ]
        has_multispectral_veg = "multispectral measurement" in query_str and ("vegetation" in query_str or "quantify" in query_str)

        matched_ndvi_explicit = has_any(ndvi_explicit_terms)
        matched_veg_quant = has_any(vegetation_quant_terms)

        is_ndvi_intent = bool(
            matched_ndvi_explicit
            or has_red_nir
            or matched_veg_quant
            or has_multispectral_veg
        )

        if is_ndvi_intent:
            all_v_matches = [m[1] for m in (matched_ndvi_explicit + matched_veg_quant)]
            if has_red_nir:
                all_v_matches.append("red and near-infrared")
            if has_multispectral_veg:
                all_v_matches.append("multispectral measurements")

            positions = []
            if matched_ndvi_explicit:
                positions.append(min(m[0] for m in matched_ndvi_explicit))
            if matched_veg_quant:
                positions.append(min(m[0] for m in matched_veg_quant))
            if has_red_nir:
                positions.append(query_str.find("red") if query_str.find("red") != -1 else query_str.find("nir"))
            if has_multispectral_veg:
                positions.append(query_str.find("multispectral"))

            first_pos = min(positions) if positions else 0
            spec = INTENT_SPECS["vegetation_analysis"].copy()
            spec["intent"] = "vegetation_analysis"
            spec["confidence"] = 0.95
            spec["reason"] = "Analytical computation of NDVI canopy vegetation index and quantification requested."
            spec["matched_keywords"] = list(set(all_v_matches)) or ["vegetation_quantification"]
            detected_intents.append((first_pos, spec))
            concepts_detected.append("vegetation_analysis")
            all_matched_keywords.extend(spec["matched_keywords"])

    # --------------------------------------------------
    # 6. SPECTRAL BAND ANALYSIS & NDWI WATER INDEX
    # --------------------------------------------------
    has_green = any(g in query_str for g in ["green information", "green measurement", "green band", "b3", " green ", "green,"])
    has_water_concept = any(w in query_str for w in ["surface water", "water body", "water bodies", "identify water", "water index", "water delineation", "open water", "lake", "river", "moisture"])
    has_nir_local = any(n in query_str for n in ["near-infrared", "near infrared", "nir", "b5"])
    is_ndwi_water_intent = (has_green and has_nir_local and has_water_concept) or ("water index" in query_str) or ("ndwi" in query_str) or ("water delineation" in query_str)

    has_four_bands = (
        ("blue" in query_str or "b2" in query_str)
        and ("green" in query_str or "b3" in query_str)
        and ("red" in query_str or "b4" in query_str)
        and (has_nir_local)
    )

    spectral_general_terms = [
        "spectral characteristics", "spectral profile", "spectral signature",
        "reflectance spectrum", "multispectral band", "multispectral bands",
        "surface reflectance across", "band ratio", "b2, b3, b4, b5", "b2-b5",
        "spectral analysis", "spectral behavior", "measurements behave across this scene"
    ]
    matched_spectral = has_any(spectral_general_terms)

    if (is_ndwi_water_intent or has_four_bands or matched_spectral) and not is_explicit_visual_only:
        all_s_matches = [m[1] for m in matched_spectral]
        pos_list = [m[0] for m in matched_spectral]

        if is_ndwi_water_intent:
            all_s_matches.append("green and near-infrared water index (NDWI)")
            pos_list.append(query_str.find("green") if query_str.find("green") != -1 else (query_str.find("water") if query_str.find("water") != -1 else 0))
            first_pos = min(pos_list) if pos_list else 0
            spec = INTENT_SPECS["water_analysis"].copy()
            spec["intent"] = "water_analysis"
            spec["operation"] = "NDWI"
            spec["confidence"] = 0.95
            spec["reason"] = "Analytical computation of McFeeters (1996) NDWI water index and moisture delineation requested."
            spec["matched_keywords"] = list(set(all_s_matches)) or ["water_index_ndwi"]
            detected_intents.append((first_pos, spec))
            concepts_detected.append("water_analysis")
            all_matched_keywords.extend(spec["matched_keywords"])
        else:
            if has_four_bands:
                all_s_matches.append("blue, green, red and near-infrared")
                pos_list.append(query_str.find("blue") if query_str.find("blue") != -1 else 0)
            first_pos = min(pos_list) if pos_list else 0
            spec = INTENT_SPECS["spectral_analysis"].copy()
            spec["intent"] = "spectral_analysis"
            spec["operation"] = "spectral_profile"
            spec["confidence"] = 0.94
            spec["reason"] = "Spectral band profile extraction across optical bands requested."
            spec["matched_keywords"] = list(set(all_s_matches)) or ["spectral_analysis"]
            detected_intents.append((first_pos, spec))
            concepts_detected.append("spectral_analysis")
            all_matched_keywords.extend(spec["matched_keywords"])

    # --------------------------------------------------
    # 7. SCENE DESCRIPTION / VISUAL VQA (VLM)
    # --------------------------------------------------
    explicit_vqa_patterns = [
        "visual reading", "visual inspection", "look at this", "take a look at this",
        "take a look", "can you take a look", "describe the scene", "describe this scene",
        "describe scene", "describe", "description",
        "describing this image to someone who cannot see it",
        "someone who cannot see it", "what are the main things visible",
        "what does this image show", "what do you see", "what can you see",
        "what can be seen", "what is visible", "what objects are visible",
        "what objects", "what features are present", "what features are visible",
        "tell me about this scene", "what is in this scene", "what is in the image",
        "noticeable plant cover"
    ]
    matched_explicit_vqa = has_any(explicit_vqa_patterns)

    visual_question_starters = [
        "is there", "are there", "does this", "do you see", "can you see",
        "can you tell", "tell me if", "what is in", "how does it look"
    ]
    matched_starters = has_any(visual_question_starters)
    visual_features = [
        "road", "roads", "highway", "building", "buildings", "house", "houses",
        "structure", "structures", "water body", "river", "lake", "pond", "canal",
        "bridge", "runway", "airport", "mountain", "hill", "plant cover", "tree", "trees"
    ]
    has_feature = any(vf in query_str for vf in visual_features)

    include_vqa = False
    if matched_explicit_vqa or is_explicit_visual_only:
        include_vqa = True
    elif matched_starters and has_feature and not any(i[1]["intent"] == "vegetation_analysis" for i in detected_intents):
        include_vqa = True
    elif not detected_intents:
        include_vqa = True

    if include_vqa:
        vqa_matches = [m[1] for m in matched_explicit_vqa] or (["visual_inspection"] if is_explicit_visual_only else ["visual_observation"])
        first_pos = min(m[0] for m in matched_explicit_vqa) if matched_explicit_vqa else 0
        spec = INTENT_SPECS["scene_description"].copy()
        spec["intent"] = "scene_description"
        spec["confidence"] = 0.90
        spec["reason"] = "Visual inspection and qualitative scene description evaluated via remote sensing Vision-Language Model."
        spec["matched_keywords"] = vqa_matches
        detected_intents.append((first_pos, spec))
        concepts_detected.append("scene_description")
        all_matched_keywords.extend(vqa_matches)

    # --------------------------------------------------
    # 8. Sort and Deduplicate by position in user's query
    # --------------------------------------------------
    detected_intents.sort(key=lambda x: x[0])
    ordered_intents = [item[1] for item in detected_intents]

    seen_intent_names = set()
    final_intents = []
    for item in ordered_intents:
        if item["intent"] not in seen_intent_names:
            seen_intent_names.add(item["intent"])
            final_intents.append(item)

    primary = final_intents[0]
    secondary = [d["intent"] for d in final_intents[1:]]

    all_modalities = []
    all_bands = []
    for item in final_intents:
        for m in item.get("required_modalities", []):
            if m not in all_modalities:
                all_modalities.append(m)
        for b in item.get("required_bands", []):
            if b not in all_bands:
                all_bands.append(b)

    is_multi_scene = any(item.get("required_scene_count") == 2 or item.get("required_scene_count") == "1 optical + 1 compatible SAR" for item in final_intents)
    max_scene_count = 2 if any(item.get("required_scene_count") == 2 for item in final_intents) else (
        "1 optical + 1 compatible SAR" if any(item.get("required_scene_count") == "1 optical + 1 compatible SAR" for item in final_intents) else 1
    )

    return {
        "success": True,
        "multi_intent": len(final_intents) > 1,
        "intent": primary["intent"],
        "tool": primary["tool"],
        "primary_intent": primary["intent"],
        "secondary_intents": secondary,
        "intents": final_intents,
        "confidence": primary["confidence"],
        "reason": primary["reason"],
        "required_modalities": all_modalities or ["optical"],
        "temporal_requirement": any(item.get("temporal_requirement") for item in final_intents),
        "required_bands": all_bands,
        "required_scene_count": max_scene_count,
        "matched_keywords": list(set(all_matched_keywords)),
        "concepts_detected": list(set(concepts_detected))
    }