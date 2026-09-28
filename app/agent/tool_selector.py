from pathlib import Path
from app.agent.tool_registry import get_tool


INTENT_TO_TOOL = {
    "vegetation_analysis": "ndvi_analysis",
    "spectral_analysis": "spectral_band_analysis",
    "water_analysis": "spectral_band_analysis",
    "ndwi_analysis": "spectral_band_analysis",
    "scene_description": "remote_sensing_vlm",
    "change_detection": "change_detection_model",
    "optical_sar_analysis": "optical_sar_model",
    "scene_metadata_retrieval": "scene_metadata_model",
    "unsupported_capability": "unsupported_capability_handler",
    "general_question": "remote_sensing_vlm"
}


def find_compatible_sar_scene(
    active_optical: dict,
    input_result: dict,
    preferred_sar_id: str | None = None
) -> dict | None:
    """
    Find a Sentinel-1 SAR scene that is compatible and spatially overlapping
    with the active optical scene.
    """
    scenes = input_result.get("scenes", [])
    sar_scenes = [
        s for s in scenes
        if s.get("modality") == "sar"
        or s.get("available_analyses", {}).get("sar_dual_pol")
        or s.get("scene_id", "").startswith("S1")
    ]
    if not sar_scenes:
        return None

    # If preferred_sar_id was explicitly provided, check that first
    if preferred_sar_id:
        for s in sar_scenes:
            if s["scene_id"] == preferred_sar_id or preferred_sar_id in s["scene_id"]:
                return s

    # 1. Match by Path/Row if both optical and SAR provide it
    opt_pr = active_optical.get("path_row")
    if opt_pr:
        for s in sar_scenes:
            if s.get("path_row") and s.get("path_row") == opt_pr:
                return s

    # 2. Check spatial bounding box overlap using rasterio
    opt_files = [
        f for f in input_result.get("files", [])
        if f.get("scene_id") == active_optical.get("scene_id") and f.get("path")
    ]
    if not opt_files:
        return None

    try:
        import rasterio
        with rasterio.open(opt_files[0]["path"]) as ds_opt:
            opt_bounds = ds_opt.bounds
            opt_crs = str(ds_opt.crs)

        for sar in sar_scenes:
            sar_files = [
                f for f in input_result.get("files", [])
                if f.get("scene_id") == sar["scene_id"] and f.get("path")
            ]
            if not sar_files:
                continue

            with rasterio.open(sar_files[0]["path"]) as ds_sar:
                sar_bounds = ds_sar.bounds
                sar_crs = str(ds_sar.crs)

                if opt_crs == sar_crs and opt_crs != "None":
                    overlap_x = max(0, min(opt_bounds.right, sar_bounds.right) - max(opt_bounds.left, sar_bounds.left))
                    overlap_y = max(0, min(opt_bounds.top, sar_bounds.top) - max(opt_bounds.bottom, sar_bounds.bottom))
                    if overlap_x > 1000 and overlap_y > 1000:
                        return sar
                else:
                    # Compare geographic bounding boxes in WGS84 (EPSG:4326)
                    sar_wgs = None
                    if ds_sar.gcps and ds_sar.gcps[0]:
                        gcps = ds_sar.gcps[0]
                        lons = [g.x for g in gcps]
                        lats = [g.y for g in gcps]
                        sar_wgs = (min(lons), min(lats), max(lons), max(lats))
                    elif ds_sar.crs and str(ds_sar.crs) != "None":
                        try:
                            from rasterio.warp import transform_bounds
                            sar_wgs = transform_bounds(ds_sar.crs, "EPSG:4326", *sar_bounds)
                        except Exception:
                            pass

                    if sar_wgs and ds_opt.crs and str(ds_opt.crs) != "None":
                        try:
                            from rasterio.warp import transform_bounds
                            opt_wgs = transform_bounds(ds_opt.crs, "EPSG:4326", *opt_bounds)
                            ol_lon = max(0.0, min(opt_wgs[2], sar_wgs[2]) - max(opt_wgs[0], sar_wgs[0]))
                            ol_lat = max(0.0, min(opt_wgs[3], sar_wgs[3]) - max(opt_wgs[1], sar_wgs[1]))
                            if ol_lon > 0.02 and ol_lat > 0.02:
                                return sar
                        except Exception:
                            pass
    except Exception:
        pass

    # If only one SAR scene exists and it has required polarizations, pair with optical
    if len(sar_scenes) == 1:
        return sar_scenes[0]

    return None


def check_tool_compatibility(
    tool_name: str,
    input_result: dict,
    active_scene: dict | None = None,
    mode: str = "single_scene",
    before_scene_id: str | None = None,
    after_scene_id: str | None = None,
    sar_scene_id: str | None = None,
    query_meta: dict | None = None,
    active_pair_type: str | None = None,
    optical_scene_id: str | None = None
):
    """
    Check whether the available input data and active scene context
    are strictly suitable for the selected tool.
    Never silently switches or substitutes the user's active scene.
    """

    # =========================================
    # GENERIC IMAGE / SINGLE-IMAGE VQA (PNG/JPEG)
    # =========================================
    if active_scene and active_scene.get("is_generic_image"):
        if tool_name == "remote_sensing_vlm":
            return {
                "compatible": True,
                "reason": (
                    "Standard RGB image routed directly to Vision-Language Model "
                    "for visual feature inspection (Scientific Band Requirement: None)."
                )
            }

        # User asked for a scientific calculation on an RGB image
        target_name = active_scene.get("source_file") or active_scene.get("title") or "selected image"
        img_fmt = active_scene.get("image_format", "PNG/JPEG")
        dims = active_scene.get("dimensions", "RGB")
        return {
            "compatible": False,
            "scientific_incompatible": True,
            "reason": (
                f"NDVI and multispectral scientific calculations require calibrated Red and Near-Infrared (NIR) "
                f"spectral bands (e.g., Landsat-9 B4 and B5 surface reflectance). The selected input "
                f"'{target_name}' is a standard RGB image ({img_fmt}, {dims}) and does not contain the required "
                f"spectral information. Scientific calculations cannot be performed on standard RGB images."
            )
        }

    # =========================================
    # NDVI ANALYSIS
    # =========================================
    if tool_name == "ndvi_analysis":
        if active_scene:
            available = active_scene.get("available_analyses", {})
            bands = active_scene.get("bands", [])
            has_b4_b5 = ("B4" in bands and "B5" in bands) or available.get("ndvi")
            if has_b4_b5:
                return {
                    "compatible": True,
                    "reason": "Red (B4) and Near-Infrared (B5) surface reflectance bands are available."
                }
            return {
                "compatible": False,
                "reason": (
                    f"NDVI requires Red (B4) and Near-Infrared (B5) spectral bands, which are not present in "
                    f"'{active_scene.get('title') or active_scene.get('scene_id')}'."
                )
            }

        for scene in input_result.get("scenes", []):
            available = scene.get("available_analyses", {})
            if available.get("ndvi"):
                return {
                    "compatible": True,
                    "reason": "Red (B4) and Near Infrared (B5) bands are available."
                }

        return {
            "compatible": False,
            "reason": "NDVI requires Red (B4) and Near Infrared (B5) bands."
        }

    # =========================================
    # SPECTRAL BAND ANALYSIS
    # =========================================
    if tool_name == "spectral_band_analysis":
        if active_scene:
            available = active_scene.get("available_analyses", {})
            bands = active_scene.get("bands", [])
            has_multispectral = ("B2" in bands and "B3" in bands and "B4" in bands and "B5" in bands) or available.get("multispectral") or available.get("ndvi")
            if has_multispectral:
                return {
                    "compatible": True,
                    "reason": "Multispectral Landsat bands (B2, B3, B4, B5) are available for spectral signature extraction."
                }
            return {
                "compatible": False,
                "reason": f"Spectral band analysis requires B2, B3, B4, and B5 Landsat surface reflectance bands on '{active_scene.get('title') or active_scene.get('scene_id')}'."
            }

        for scene in input_result.get("scenes", []):
            available = scene.get("available_analyses", {})
            if available.get("multispectral") or available.get("ndvi"):
                return {
                    "compatible": True,
                    "reason": "Multispectral Landsat bands (B2, B3, B4, B5) are available for spectral signature extraction."
                }

        return {
            "compatible": False,
            "reason": "Spectral band analysis requires B2, B3, B4, and B5 Landsat surface reflectance bands."
        }

    # =========================================
    # CHANGE DETECTION (Bi-Temporal Pair)
    # Architecture Rule: Do NOT auto-pick available_pairs[0]
    # =========================================
    if tool_name == "change_detection_model":
        if mode in {"multimodal_pair", "fusion"} or active_pair_type == "optical_sar":
            return {
                "compatible": False,
                "reason": "Change detection requires a compatible before/after scene pair. The current analysis context is an Optical + SAR multimodal pair, not a bi-temporal change pair."
            }

        # Case A: Explicitly confirmed before & after scenes
        if mode == "bitemporal" or (before_scene_id and after_scene_id):
            if before_scene_id and after_scene_id:
                return {
                    "compatible": True,
                    "reason": f"Bi-temporal pair confirmed: {before_scene_id} -> {after_scene_id}."
                }
            return {
                "compatible": False,
                "reason": "Bi-temporal change detection requires both Before and After scenes to be confirmed."
            }

        # Case B: User has an active single scene selected in single / single_scene mode
        if active_scene and mode in {"single", "single_scene"}:
            return {
                "compatible": False,
                "reason": "Change detection requires a compatible before/after scene pair. The current analysis context contains only one scene. Please select a bi-temporal pair."
            }

        # Case C: General catalog check when no specific scene is active
        pairs = input_result.get("bi_temporal_pairs", [])
        if not pairs:
            return {
                "compatible": False,
                "reason": "Change detection requires a compatible before/after scene pair. The current analysis context contains only one scene. Please select a bi-temporal pair."
            }
        if len(pairs) > 1:
            return {
                "compatible": False,
                "reason": (
                    "Multiple bi-temporal pairs exist in the catalog. "
                    "Please select which pair to analyze."
                )
            }
        if len(pairs) == 1 and not active_scene and query_meta and query_meta.get("temporal_requirement"):
            return {
                "compatible": True,
                "reason": "A valid bi-temporal pair was detected with before and after scenes."
            }

        return {
            "compatible": False,
            "reason": "Change detection requires a compatible before/after scene pair. The current analysis context contains only one scene. Please select a bi-temporal pair."
        }

    # =========================================
    # OPTICAL + SAR FUSION
    # Architecture Rule: Active optical scene must match compatible SAR scene
    # =========================================
    if tool_name == "optical_sar_model":
        if mode in {"multimodal_pair", "fusion"} or active_pair_type == "optical_sar":
            opt_id = optical_scene_id or (active_scene.get("scene_id") if active_scene else None)
            if opt_id and sar_scene_id:
                return {
                    "compatible": True,
                    "compatible_sar_scene": sar_scene_id,
                    "reason": f"Active Optical + SAR pair selected: Optical '{opt_id}' + SAR '{sar_scene_id}'."
                }

        if not active_scene:
            return {
                "compatible": False,
                "reason": "Optical + SAR analysis requires an active optical scene to be selected."
            }

        # Ensure active scene is optical
        is_optical = "optical" in active_scene.get("modality", "optical").lower() or active_scene.get("scene_id", "").startswith(("LC", "S2"))
        if not is_optical:
            return {
                "compatible": False,
                "reason": "The selected active scene is not an optical scene."
            }

        # Find compatible SAR scene for THIS active optical scene
        compatible_sar = find_compatible_sar_scene(active_scene, input_result, preferred_sar_id=sar_scene_id)
        if not compatible_sar:
            return {
                "compatible": False,
                "reason": (
                    "Optical + SAR analysis requires a compatible SAR scene. "
                    "The currently selected scene is optical-only. "
                    "Please select or upload a compatible Sentinel-1 SAR scene."
                )
            }

        return {
            "compatible": True,
            "compatible_sar_scene": compatible_sar["scene_id"],
            "reason": f"Compatible Sentinel-1 SAR scene '{compatible_sar['scene_id']}' matches active optical scene '{active_scene['scene_id']}'."
        }

    # =========================================
    # SCENE METADATA MODEL (Deterministic)
    # =========================================
    if tool_name == "scene_metadata_model":
        if active_scene or (input_result and input_result.get("scenes")):
            return {
                "compatible": True,
                "reason": "Authoritative observation metadata is available for deterministic retrieval."
            }
        return {
            "compatible": False,
            "reason": "Metadata retrieval requires an active or available scene in the workspace."
        }

    # =========================================
    # UNSUPPORTED CAPABILITY HANDLER
    # =========================================
    if tool_name == "unsupported_capability_handler":
        return {
            "compatible": True,
            "reason": "Direct capability-boundary response."
        }

    # =========================================
    # REMOTE SENSING VLM / GENERAL
    # =========================================
    return {
        "compatible": True,
        "reason": "Visual remote sensing inspection routed to fine-tuned Vision-Language Model (Scientific Band Requirement: None)."
    }


def select_tools(
    intents: list,
    input_result: dict | None = None,
    active_scene: dict | None = None,
    mode: str = "single_scene",
    before_scene_id: str | None = None,
    after_scene_id: str | None = None,
    sar_scene_id: str | None = None,
    query_meta: dict | None = None,
    active_pair_type: str | None = None,
    optical_scene_id: str | None = None
) -> dict:
    """
    Evaluates tool compatibility and readiness for a list of requested intents.
    Supports multi-intent query handling where individual intents can be 'ready'
    or 'blocked', without discarding compatible intents.
    """
    if not intents:
        return {
            "success": False,
            "tools": [],
            "ready_tools": [],
            "blocked_tools": [],
            "reason": "No intents were provided."
        }

    tool_plans = []
    ready_tools = []
    blocked_tools = []

    for item in intents:
        if isinstance(item, dict):
            intent_name = item.get("intent")
            intent_spec = item
        else:
            intent_name = str(item)
            intent_spec = {"intent": intent_name}

        tool_name = INTENT_TO_TOOL.get(intent_name)
        if not tool_name:
            entry = {
                "intent": intent_name,
                "tool": None,
                "description": "Unsupported analysis operation",
                "status": "unsupported",
                "compatible": False,
                "reason": f"No analysis tool is registered for intent '{intent_name}'.",
                "compatibility_reason": f"No analysis tool is registered for intent '{intent_name}'.",
                "scientific_incompatible": False,
                "spec": intent_spec
            }
            tool_plans.append(entry)
            blocked_tools.append(entry)
            continue

        tool = get_tool(tool_name)
        if not tool:
            entry = {
                "intent": intent_name,
                "tool": tool_name,
                "description": "Unregistered tool",
                "status": "unregistered",
                "compatible": False,
                "reason": f"Tool '{tool_name}' is not registered in tool registry.",
                "compatibility_reason": f"Tool '{tool_name}' is not registered in tool registry.",
                "scientific_incompatible": False,
                "spec": intent_spec
            }
            tool_plans.append(entry)
            blocked_tools.append(entry)
            continue

        comp = check_tool_compatibility(
            tool_name=tool_name,
            input_result=input_result,
            active_scene=active_scene,
            mode=mode,
            before_scene_id=before_scene_id,
            after_scene_id=after_scene_id,
            sar_scene_id=sar_scene_id,
            query_meta=query_meta,
            active_pair_type=active_pair_type,
            optical_scene_id=optical_scene_id
        )

        entry = {
            "intent": intent_name,
            "tool": tool_name,
            "description": tool.description,
            "status": "ready" if comp["compatible"] else "blocked",
            "compatible": comp["compatible"],
            "reason": comp.get("reason", ""),
            "compatibility_reason": comp.get("reason", ""),
            "scientific_incompatible": comp.get("scientific_incompatible", False),
            "compatible_sar_scene": comp.get("compatible_sar_scene"),
            "spec": intent_spec
        }

        tool_plans.append(entry)
        if comp["compatible"]:
            ready_tools.append(entry)
        else:
            blocked_tools.append(entry)

    overall_success = len(ready_tools) > 0

    return {
        "success": overall_success,
        "tools": tool_plans,
        "ready_tools": ready_tools,
        "blocked_tools": blocked_tools,
        "all_blocked": len(ready_tools) == 0,
        "primary_tool": ready_tools[0] if ready_tools else (blocked_tools[0] if blocked_tools else None)
    }


def select_tool(
    intent: str,
    input_result: dict | None = None,
    active_scene: dict | None = None,
    mode: str = "single_scene",
    before_scene_id: str | None = None,
    after_scene_id: str | None = None,
    sar_scene_id: str | None = None,
    query_meta: dict | None = None
):
    plan = select_tools(
        intents=[intent],
        input_result=input_result,
        active_scene=active_scene,
        mode=mode,
        before_scene_id=before_scene_id,
        after_scene_id=after_scene_id,
        sar_scene_id=sar_scene_id,
        query_meta=query_meta
    )
    if not plan["tools"]:
        return {
            "success": False,
            "intent": intent,
            "tool": None,
            "reason": plan.get("reason", "No tool selected.")
        }
    entry = plan["tools"][0]
    return {
        "success": entry["compatible"],
        "intent": entry["intent"],
        "tool": entry["tool"],
        "description": entry["description"],
        "status": entry["status"],
        "compatible": entry["compatible"],
        "reason": entry["reason"],
        "compatibility_reason": entry["compatibility_reason"],
        "scientific_incompatible": entry["scientific_incompatible"],
        "compatible_sar_scene": entry.get("compatible_sar_scene")
    }