from pathlib import Path

from app.agent.input_analyzer import analyze_input
from app.agent.query_parser import parse_query
from app.agent.tool_selector import select_tool, select_tools
from app.agent.tool_executor import execute_tool
from app.agent.result_interpreter import (
    interpret_ndvi_result,
    interpret_change_detection_result,
    interpret_vlm_result,
    interpret_spectral_result,
    interpret_optical_sar_result,
    interpret_metadata_result,
    interpret_unsupported_result
)
from app.agent.execution_trace import ExecutionTrace


def fuse_multi_intent_results(
    raw_query: str,
    query_result: dict,
    executed_components: list,
    blocked_components: list,
    active_scene_meta: dict | None,
    mode: str,
    before_scene_id: str | None = None,
    after_scene_id: str | None = None
) -> tuple[dict, dict, list[str]]:
    """
    Combines outputs, statistics, visual evidence, and qualitative interpretations
    from multiple executed and blocked operations into an authoritative unified payload.
    """
    combined_analysis = {}
    combined_evidence = {}
    selected_tools = []

    # 1. Merge evidence
    for c in executed_components:
        if c.get("evidence"):
            combined_evidence.update(c["evidence"])
        if c.get("tool") and c["tool"] not in selected_tools:
            selected_tools.append(c["tool"])

    combined_analysis["evidence"] = combined_evidence

    # 2. Merge statistics and metrics from all executed components
    for c in executed_components:
        res = c.get("execution_result", {})
        if "ndvi_statistics" in res:
            combined_analysis["ndvi_statistics"] = res["ndvi_statistics"]
            combined_analysis["mean_ndvi"] = res["ndvi_statistics"].get("mean_ndvi") if res["ndvi_statistics"].get("mean_ndvi") is not None else res["ndvi_statistics"].get("mean")
        if "statistics" in res:
            combined_analysis["statistics"] = res["statistics"]
            combined_analysis["mean_delta_ndvi"] = res["statistics"].get("mean_delta_ndvi")
        if "spectral_indices" in res:
            combined_analysis["spectral_indices"] = res["spectral_indices"]
        if "spectral_signature_classification" in res:
            combined_analysis["spectral_signature_classification"] = res["spectral_signature_classification"]
        if "optical_metrics" in res:
            combined_analysis["optical_metrics"] = res["optical_metrics"]
        if "sar_metrics" in res:
            combined_analysis["sar_metrics"] = res["sar_metrics"]
        if "fusion_metrics" in res:
            combined_analysis["fusion_metrics"] = res["fusion_metrics"]
        if "answer" in res:
            combined_analysis["answer"] = res["answer"]
        if "model" in res:
            combined_analysis["model"] = res["model"]
        if "before" in res:
            combined_analysis["before"] = res["before"]
        if "after" in res:
            combined_analysis["after"] = res["after"]
        if "provenance" in res:
            combined_analysis["provenance"] = res["provenance"]
        if "metadata_audit" in res:
            combined_analysis["metadata_audit"] = res["metadata_audit"]
        if "optical_scene" in res:
            combined_analysis["optical_scene"] = res["optical_scene"]
        if "sar_scene" in res:
            combined_analysis["sar_scene"] = res["sar_scene"]

    # 3. Build components list for frontend rendering
    components_list = []
    for c in executed_components:
        is_vlm = c["tool"] == "remote_sensing_vlm"
        is_vlm_bypassed = is_vlm and (
            c["execution_result"].get("deployment_constrained")
            or not c["execution_result"].get("vlm_available", True)
        )
        status_val = "bypassed" if is_vlm_bypassed else "executed"

        components_list.append({
            "intent": c["intent"],
            "tool": c["tool"],
            "tool_name": c["tool"],
            "status": status_val,
            "title": c["title"],
            "message": c["interpretation"].get("summary") or c["interpretation"].get("interpretation", ""),
            "summary": c["interpretation"].get("summary") or c["interpretation"].get("interpretation", ""),
            "metrics": (
                c["execution_result"].get("statistics")
                or c["execution_result"].get("ndvi_statistics")
                or c["execution_result"].get("spectral_indices")
                or {}
            ),
            "evidence": c.get("evidence", {})
        })
    for b in blocked_components:
        b_title = b.get("title") or b.get("description") or b.get("tool") or "Component"
        b_reason = b.get("reason", "")
        components_list.append({
            "intent": b.get("intent", ""),
            "tool": b.get("tool"),
            "tool_name": b.get("tool"),
            "status": "blocked",
            "title": b_title,
            "message": b_reason,
            "summary": b_reason,
            "error": b_reason
        })
    combined_analysis["components"] = components_list

    # 4. Multi-Intent Interpretation Synthesis
    # If only 1 executed component and 0 blocked, use its interpretation directly
    if len(executed_components) == 1 and not blocked_components:
        primary_interp = executed_components[0]["interpretation"]
        return combined_analysis, primary_interp, selected_tools

    # Multi-component synthesis
    sections = []
    section_idx = 1
    basis_factors = []
    conf_scores = []
    dynamic_class = None
    veg_category = None

    for c in executed_components:
        t = c["tool"]
        interp = c["interpretation"]
        text = interp.get("interpretation") or interp.get("summary", "")
        if interp.get("dynamic_classification"):
            dynamic_class = interp.get("dynamic_classification")
        if interp.get("vegetation_category"):
            veg_category = interp.get("vegetation_category")

        conf_data = interp.get("confidence", {})
        if isinstance(conf_data, dict):
            conf_scores.append(conf_data.get("score", 0.85))
            if conf_data.get("basis"):
                basis_factors.extend(conf_data.get("basis"))
        elif isinstance(conf_data, (int, float)):
            conf_scores.append(float(conf_data))

        if t == "ndvi_analysis":
            stats = c["execution_result"].get("ndvi_statistics", {})
            m = stats.get("mean_ndvi") if stats.get("mean_ndvi") is not None else stats.get("mean", 0.0)
            std = stats.get("stddev", 0.0)
            cat = interp.get("vegetation_category", "Vegetation canopy")
            sec = f"### {section_idx}. NDVI & Vegetation Canopy\n\n"
            sec += f"• **Mean NDVI:** `{m:+.3f}` (±{std:.3f})\n"
            sec += f"• **Canopy Density Classification:** {cat}\n\n"
            sec += f"{text}"
            sections.append(sec)
            section_idx += 1

        elif t == "spectral_band_analysis":
            indices = c["execution_result"].get("spectral_indices", {})
            m_ndwi = indices.get("mean_ndwi", 0.0)
            sig = c["execution_result"].get("spectral_signature_classification", "Spectral analysis")
            sec = f"### {section_idx}. Spectral Profile & Water Delineation (NDWI)\n\n"
            sec += f"• **Mean NDWI (McFeeters 1996):** `{m_ndwi:+.3f}`\n"
            sec += f"• **Spectral Signature Classification:** {sig}\n\n"
            sec += f"{text}"
            sections.append(sec)
            section_idx += 1

        elif t == "change_detection_model":
            stats = c["execution_result"].get("statistics", {})
            b_mean = stats.get("baseline_mean_ndvi", 0.0)
            a_mean = stats.get("monitoring_mean_ndvi", 0.0)
            d_mean = stats.get("mean_delta_ndvi", 0.0)
            gain = stats.get("vegetation_gain_percentage", 0.0)
            loss = stats.get("vegetation_loss_percentage", 0.0)
            stable = stats.get("stable_percentage", 0.0)
            sec = f"### {section_idx}. Bi-Temporal Change Analysis\n\n"
            sec += f"• **Baseline Mean (T1):** `{b_mean:.4f}` | **Monitoring Mean (T2):** `{a_mean:.4f}`\n"
            sec += f"• **Net Delta (ΔNDVI):** `{d_mean:+.4f}`\n"
            sec += f"• **Vegetation Gain:** `{gain:.1f}%` | **Loss:** `{loss:.1f}%` | **Stable:** `{stable:.1f}%`\n\n"
            sec += f"{text}"
            sections.append(sec)
            section_idx += 1

        elif t == "optical_sar_model":
            fus = c["execution_result"].get("fusion_metrics", {})
            cls_env = fus.get("environmental_classification", "Multimodal terrain")
            sec = f"### {section_idx}. Optical + SAR Radar Fusion\n\n"
            sec += f"• **Environmental Classification:** {cls_env}\n\n"
            sec += f"{text}"
            sections.append(sec)
            section_idx += 1

        elif t == "remote_sensing_vlm":
            ans = c["execution_result"].get("answer", "")
            sec = f"### {section_idx}. Visual Remote Sensing Inspection\n\n{ans}"
            sections.append(sec)
            section_idx += 1

        elif t == "scene_metadata_model":
            sec = f"### {section_idx}. Authoritative Scene Metadata\n\n{text}"
            sections.append(sec)
            section_idx += 1

        elif t == "unsupported_capability_handler":
            sec = f"### {section_idx}. Operational Capability Boundary\n\n{text}"
            sections.append(sec)
            section_idx += 1

    # Append blocked components (e.g. change detection missing temporal pair)
    for b in blocked_components:
        b_title = b.get("title") or b.get("description") or b.get("tool") or "Component Requirement"
        b_reason = b.get("reason", "")
        sec = f"### {section_idx}. {b_title}\n\n"
        sec += f"> ⚠ **Notice:** {b_reason}\n"
        sections.append(sec)
        section_idx += 1

    full_summary = "\n\n---\n\n".join(sections)
    avg_score = round(sum(conf_scores) / max(len(conf_scores), 1), 2)
    conf_level = "high" if avg_score >= 0.80 else ("medium" if avg_score >= 0.60 else "low")

    combined_interpretation = {
        "success": True,
        "interpretation": full_summary,
        "summary": full_summary,
        "headline": "Multi-Dimensional Satellite Analysis",
        "dynamic_classification": dynamic_class,
        "vegetation_category": veg_category,
        "confidence": {
            "score": avg_score,
            "level": conf_level,
            "basis": list(set(basis_factors)) if basis_factors else ["Multi-component analysis executed."]
        },
        "basis": {
            "components_count": len(executed_components),
            "blocked_count": len(blocked_components)
        }
    }

    return combined_analysis, combined_interpretation, selected_tools


def process_user_query(
    query: str,
    scene_id: str | None = None,
    active_scene_id: str | None = None,
    active_scene_files: list[str] | None = None,
    selected_scenario: str | None = None,
    mode: str = "single_scene",
    before_scene_id: str | None = None,
    after_scene_id: str | None = None,
    optical_scene_id: str | None = None,
    sar_scene_id: str | None = None,
    active_pair_type: str | None = None,
    active_pair_id: str | None = None,
    workspace_id: str | None = None
):
    scene_id = active_scene_id or scene_id
    trace = ExecutionTrace(query)

    # -----------------------------------------
    # STEP 1 — Analyze input data & validate scene context
    # -----------------------------------------

    trace.add_step(
        step="input_analysis",
        status="started"
    )

    from app.services.workspace_manager import workspace_manager
    ws_dir = workspace_manager.get_workspace_dir(workspace_id)
    ws_id = workspace_manager.sanitize_workspace_id(workspace_id)

    manifest_file = ws_dir / "workspace_manifest.json"
    is_cleared = False
    if manifest_file.exists():
        try:
            with open(manifest_file, "r") as f:
                is_cleared = json.load(f).get("cleared", False)
        except Exception:
            pass

    has_ws_files = any(
        f.is_file() and f.suffix.lower() in {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
        for f in ws_dir.iterdir()
    ) if ws_dir.exists() else False

    search_dirs = [ws_dir]
    if not is_cleared:
        default_ws = workspace_manager.get_workspace_dir("satquery_default")
        if ws_dir.resolve() != default_ws.resolve() and default_ws.exists():
            search_dirs.append(default_ws)
        if Path("uploads").resolve() != ws_dir.resolve():
            search_dirs.append(Path("uploads"))

    input_result = analyze_input(
        search_dirs
    )
    upload_dir = ws_dir if has_ws_files else Path("uploads")

    if not input_result["success"]:

        trace.add_step(
            step="input_analysis",
            status="failed",
            details=input_result
        )

        trace.complete()

        return {
            **input_result,
            "execution_trace": trace.to_dict()
        }

    # -----------------------------------------
    # STEP 1 — Understand the query
    # -----------------------------------------

    trace.add_step(
        step="query_parsing",
        status="started"
    )

    query_result = parse_query(query)

    if not query_result["success"]:
        trace.add_step(
            step="query_parsing",
            status="failed",
            details=query_result
        )
        trace.complete()
        return {
            **query_result,
            "execution_trace": trace.to_dict()
        }

    is_unsupported = query_result.get("primary_intent") == "unsupported_capability"

    # Strict Validation: For single scene queries, a scene MUST be explicitly provided
    if mode == "single_scene" and not scene_id and not is_unsupported:
        trace.add_step(
            step="input_analysis",
            status="failed",
            details={
                "error": "The previous scene was removed or no scene is selected. Select another scene to continue analysis."
            }
        )
        trace.complete()
        return {
            "success": False,
            "query": query,
            "intent": "none",
            "selected_tool": "none",
            "error": "The previous scene was removed. Select another scene to continue.",
            "execution_trace": trace.to_dict()
        }

    # Strict Validation: For bi-temporal queries, both scenes must be confirmed
    if mode == "bitemporal" and (not before_scene_id or not after_scene_id):
        trace.add_step(
            step="input_analysis",
            status="failed",
            details={
                "error": "Bi-temporal analysis requires both a Before scene and an After scene to be confirmed."
            }
        )
        trace.complete()
        return {
            "success": False,
            "query": query,
            "intent": "change_detection",
            "selected_tool": "change_detection_model",
            "error": "Bi-temporal analysis requires both a Before scene and an After scene to be confirmed.",
            "execution_trace": trace.to_dict()
        }

    optical_scene_meta = None
    sar_scene_meta = None

    # Strict Validation: For multimodal pair queries, both scenes must be confirmed and present
    if mode in {"multimodal_pair", "fusion"} or active_pair_type == "optical_sar":
        opt_target = optical_scene_id or scene_id
        sar_target = sar_scene_id
        if not opt_target or not sar_target:
            trace.add_step(
                step="input_analysis",
                status="failed",
                details={
                    "error": "Multimodal pair analysis requires both an Optical scene and a SAR scene to be confirmed."
                }
            )
            trace.complete()
            return {
                "success": False,
                "query": query,
                "intent": "optical_sar_analysis",
                "selected_tool": "optical_sar_model",
                "error": "Multimodal pair analysis requires both an Optical scene and a SAR scene to be confirmed.",
                "execution_trace": trace.to_dict()
            }

        for s in input_result.get("scenes", []):
            if s["scene_id"] == opt_target or opt_target in s["scene_id"] or s["scene_id"] in opt_target:
                optical_scene_meta = s
            if s["scene_id"] == sar_target or sar_target in s["scene_id"] or s["scene_id"] in sar_target:
                sar_scene_meta = s

        if (not optical_scene_meta or not sar_scene_meta) and not is_unsupported:
            trace.add_step(
                step="input_analysis",
                status="failed",
                details={
                    "error": "The previous scene was removed. Select another scene to continue."
                }
            )
            trace.complete()
            return {
                "success": False,
                "query": query,
                "intent": "optical_sar_analysis",
                "selected_tool": "optical_sar_model",
                "error": "The previous scene was removed. Select another scene to continue.",
                "execution_trace": trace.to_dict()
            }

        active_scene_meta = optical_scene_meta
        scene_id = optical_scene_meta["scene_id"]
        optical_scene_id = optical_scene_meta["scene_id"]
        sar_scene_id = sar_scene_meta["scene_id"]

    # Find matching active scene in catalog (Single scene mode)
    else:
        active_scene_meta = None
        if scene_id:
            for s in input_result.get("scenes", []):
                if s["scene_id"] == scene_id or scene_id in s["scene_id"] or s["scene_id"] in scene_id:
                    active_scene_meta = s
                    scene_id = s["scene_id"]
                    break

            if active_scene_meta:
                if active_scene_meta.get("modality", "optical").lower() == "optical" or active_scene_meta.get("scene_id", "").startswith(("LC", "S2")):
                    optical_scene_meta = active_scene_meta
                elif "sar" in active_scene_meta.get("modality", "").lower() or active_scene_meta.get("scene_id", "").startswith("S1"):
                    sar_scene_meta = active_scene_meta

            if not active_scene_meta and not is_unsupported:
                trace.add_step(
                    step="input_analysis",
                    status="failed",
                    details={
                        "error": f"The previous scene was removed. Select another scene to continue."
                    }
                )
                trace.complete()
                return {
                    "success": False,
                    "query": query,
                    "intent": "none",
                    "selected_tool": "none",
                    "error": "The previous scene was removed. Select another scene to continue.",
                    "execution_trace": trace.to_dict()
                }

    is_generic_active = bool(active_scene_meta and active_scene_meta.get("is_generic_image"))

    if is_generic_active:
        trace.add_step(
            step="input_analysis",
            status="completed",
            details={
                "input_type": "Single RGB Image",
                "image_format": active_scene_meta.get("image_format", "PNG"),
                "dimensions": active_scene_meta.get("dimensions", "RGB"),
                "channels": active_scene_meta.get("channels", "RGB"),
                "geospatial_metadata": "Not available",
                "selected_scene": active_scene_meta.get("title", scene_id),
                "selected_scene_id": scene_id,
                "source_file": active_scene_meta.get("source_file"),
                "upload_timestamp": active_scene_meta.get("upload_timestamp"),
                "file_count": 1,
                "scene_count": input_result.get("scene_count", 1)
            }
        )
    else:
        trace.add_step(
            step="input_analysis",
            status="completed",
            details={
                "file_count": input_result["file_count"],
                "scene_count": input_result["scene_count"],
                "input_type": input_result["input_type"],
                "selected_scene": active_scene_meta.get("title") if active_scene_meta else (f"{before_scene_id} -> {after_scene_id}" if mode == "bitemporal" else scene_id),
                "selected_scene_id": scene_id,
                "sensor": active_scene_meta.get("sensor") if active_scene_meta else None,
                "acquisition_date": active_scene_meta.get("acquisition_date") if active_scene_meta else None,
                "path_row": active_scene_meta.get("path_row_formatted") if active_scene_meta else None,
                "crs": active_scene_meta.get("crs") if active_scene_meta else None,
                "query_mode": mode,
                "before_scene_id": before_scene_id,
                "after_scene_id": after_scene_id,
                "optical_scene_id": optical_scene_id,
                "sar_scene_id": sar_scene_id,
                "active_pair_type": active_pair_type,
                "active_pair_id": active_pair_id
            }
        )

    display_intent = "Scene / Visual Question Answering" if (is_generic_active and query_result["intent"] == "scene_description") else query_result["intent"]
    trace.add_step(
        step="query_parsing",
        status="completed",
        details={
            "intent": display_intent,
            "reason": query_result["reason"]
        }
    )

    # -----------------------------------------
    # STEP 2 — Select tool & Active Input Validation
    # ---------------------------------------    # -----------------------------------------
    # STEP 2 — Multi-Intent Detection & Tool Selection
    # -----------------------------------------

    requested_intents = query_result.get("intents") or [{"intent": query_result["intent"]}]

    if query_result.get("multi_intent"):
        trace.add_step(
            step="multi_intent_detection",
            status="completed",
            details={
                "detected_intents": [item["intent"] for item in requested_intents],
                "primary_intent": query_result.get("primary_intent"),
                "secondary_intents": query_result.get("secondary_intents", [])
            }
        )

    trace.add_step(
        step="tool_selection",
        status="started"
    )

    tool_plan = select_tools(
        intents=requested_intents,
        input_result=input_result,
        active_scene=active_scene_meta,
        mode=mode,
        before_scene_id=before_scene_id,
        after_scene_id=after_scene_id,
        sar_scene_id=sar_scene_id,
        query_meta=query_result,
        active_pair_type=active_pair_type,
        optical_scene_id=optical_scene_id
    )

    ready_tools = tool_plan.get("ready_tools", [])
    blocked_tools = tool_plan.get("blocked_tools", [])

    has_optical = False
    has_compatible_sar = False
    if active_scene_meta:
        if active_scene_meta.get("is_generic_image") or "optical" in active_scene_meta.get("modality", "optical").lower() or active_scene_meta.get("scene_id", "").startswith(("LC", "S2")):
            has_optical = True
        for t in ready_tools:
            if t.get("compatible_sar_scene"):
                has_compatible_sar = True
                sar_scene_id = t.get("compatible_sar_scene")

    req_modalities = query_result.get("required_modalities", ["optical"])
    req_str = " + ".join(m.capitalize() for m in req_modalities)

    # If ALL requested tools are blocked: return structured rejection
    if tool_plan.get("all_blocked"):
        primary_blocked = blocked_tools[0] if blocked_tools else {}
        rejection_reason = primary_blocked.get(
            "reason",
            "The requested analysis is incompatible with the selected active scene."
        )

        trace.add_step(
            step="active_input_validation",
            status="blocked",
            details={
                "active_scene": active_scene_meta.get("title", scene_id) if active_scene_meta else scene_id,
                "active_scene_id": scene_id,
                "required": f"{req_str} (Required count: {query_result.get('required_scene_count', 1)})",
                "available": f"Optical {'✓' if has_optical else '✗'}, SAR {'✓' if has_compatible_sar else '✗'}",
                "decision": f"Analysis blocked — {rejection_reason}"
            }
        )

        trace.add_step(
            step="tool_selection",
            status="failed",
            details={
                "tool": primary_blocked.get("tool", "none"),
                "compatible": False,
                "reason": rejection_reason
            }
        )
        trace.complete()

        analyzed_scene = {
            "source_scene_id": active_scene_meta.get("scene_id") if active_scene_meta else scene_id,
            "source_scene_name": active_scene_meta.get("title", scene_id) if active_scene_meta else scene_id,
            "source_sensor": active_scene_meta.get("sensor", "Visual Sensor") if active_scene_meta else "Visual Sensor",
            "source_dates": active_scene_meta.get("acquisition_date") or active_scene_meta.get("date") if active_scene_meta else None,
            "source_modality": active_scene_meta.get("modality", "optical") if active_scene_meta else "optical",
            "source_bands": active_scene_meta.get("bands", ["RGB"]) if active_scene_meta else ["RGB"],
            "scene_id": active_scene_meta.get("scene_id") if active_scene_meta else scene_id,
            "title": active_scene_meta.get("title", scene_id) if active_scene_meta else scene_id,
            "satellite": active_scene_meta.get("satellite", "Standard Image") if active_scene_meta else "Standard Image",
            "sensor": active_scene_meta.get("sensor", "Visual Sensor") if active_scene_meta else "Visual Sensor",
            "date": active_scene_meta.get("date", "Active Scene") if active_scene_meta else "Active Scene",
            "acquisition_date": active_scene_meta.get("acquisition_date") if active_scene_meta else None,
            "path_row_formatted": active_scene_meta.get("path_row_formatted") if active_scene_meta else None,
            "resolution": active_scene_meta.get("resolution", "30 m") if active_scene_meta else "30 m",
            "crs": active_scene_meta.get("crs", "EPSG:32645") if active_scene_meta else "EPSG:32645",
            "thumbnail": active_scene_meta.get("thumbnail") if active_scene_meta else None,
            "bands": active_scene_meta.get("bands", []) if active_scene_meta else [],
            "mode": mode
        }

        is_sci_incomp = bool(primary_blocked.get("scientific_incompatible") or (is_generic_active and primary_blocked.get("tool") in {"ndvi_analysis", "spectral_band_analysis"}))

        return {
            "success": True if is_sci_incomp else False,
            "query": query,
            "intent": query_result["intent"],
            "intent_reason": query_result["reason"],
            "selected_tool": primary_blocked.get("tool", "none"),
            "tool_description": primary_blocked.get("description", "Input Compatibility Validation"),
            "source_scene_id": analyzed_scene["source_scene_id"],
            "source_scene_name": analyzed_scene["source_scene_name"],
            "source_dates": analyzed_scene["source_dates"],
            "source_sensor": analyzed_scene["source_sensor"],
            "source_modality": analyzed_scene["source_modality"],
            "source_bands": analyzed_scene["source_bands"],
            "error": rejection_reason,
            "analyzed_scene": analyzed_scene,
            "analysis": {
                "success": False,
                "scientific_incompatible": is_sci_incomp,
                "error": rejection_reason,
                "explanation": rejection_reason,
                "required_bands": ["Red (B4)", "NIR (B5)"],
                "available_bands": active_scene_meta.get("bands", ["RGB"]) if active_scene_meta else ["RGB"]
            },
            "interpretation": {
                "headline": "Multispectral Bands Required" if is_sci_incomp else "Input Compatibility Notice",
                "summary": rejection_reason,
                "scientific_note": rejection_reason,
                "confidence": 1.0,
                "evidence_score": 0.0,
                "confidence_basis": [
                    {"factor": "Input Image Format", "assessment": f"Standard {active_scene_meta.get('image_format', 'RGB') if active_scene_meta else 'RGB'} imagery"} if is_sci_incomp else {"factor": "Active Scene Context", "assessment": active_scene_meta.get("title", scene_id) if active_scene_meta else "Active Scene"},
                    {"factor": "Active Input Validation", "assessment": "Requirements unsatisfied"}
                ]
            },
            "execution_trace": trace.to_dict()
        }

    # At least one tool is ready: Log active input validation for each tool
    for r_tool in ready_tools:
        trace.add_step(
            step="active_input_validation",
            status="completed",
            details={
                "tool": r_tool["tool"],
                "intent": r_tool["intent"],
                "active_scene": active_scene_meta.get("title", scene_id) if active_scene_meta else scene_id,
                "active_scene_id": scene_id,
                "decision": "Compatibility: VALID",
                "reason": r_tool.get("compatibility_reason", "")
            }
        )

    for b_tool in blocked_tools:
        trace.add_step(
            step="active_input_validation",
            status="blocked",
            details={
                "tool": b_tool["tool"],
                "intent": b_tool["intent"],
                "active_scene": active_scene_meta.get("title", scene_id) if active_scene_meta else scene_id,
                "active_scene_id": scene_id,
                "decision": f"Component blocked — {b_tool.get('reason', '')}"
            }
        )

    trace.add_step(
        step="tool_selection",
        status="completed",
        details={
            "selected_tools": [t["tool"] for t in ready_tools],
            "blocked_tools": [t["tool"] for t in blocked_tools],
            "total_requested": len(tool_plan.get("tools", []))
        }
    )

    # -----------------------------------------
    # STEP 3 — Execute each ready tool
    # -----------------------------------------

    executed_components = []

    for tool_item in ready_tools:
        tool_name = tool_item["tool"]
        intent_name = tool_item["intent"]

        target_id = scene_id
        current_active_meta = active_scene_meta

        if mode == "bitemporal" and tool_name in {"ndvi_analysis", "spectral_band_analysis", "remote_sensing_vlm"}:
            target_id = after_scene_id or before_scene_id or scene_id

        # Authoritative routing for metadata requests in multimodal context
        if tool_name == "scene_metadata_model":
            if mode in {"multimodal_pair", "fusion"} or active_pair_type == "optical_sar":
                wants_sar = any(k in query.lower() for k in ["sar", "radar", "microwave", "sentinel-1"])
                if wants_sar and sar_scene_meta:
                    target_id = sar_scene_meta.get("scene_id")
                    current_active_meta = sar_scene_meta
                else:
                    target_id = optical_scene_meta.get("scene_id") if optical_scene_meta else scene_id
                    current_active_meta = optical_scene_meta

        # Execution trace logging with exact scene identifiers
        if tool_name == "optical_sar_model":
            resolved_sar_id = sar_scene_id or tool_item.get("compatible_sar_scene")
            if not sar_scene_meta and resolved_sar_id:
                for s in input_result.get("scenes", []):
                    if s["scene_id"] == resolved_sar_id or resolved_sar_id in s["scene_id"]:
                        sar_scene_meta = s
                        break
            if not optical_scene_meta and (optical_scene_id or target_id):
                target_opt = optical_scene_id or target_id
                for s in input_result.get("scenes", []):
                    if s["scene_id"] == target_opt or target_opt in s["scene_id"]:
                        optical_scene_meta = s
                        break

            opt_d = (optical_scene_meta.get("acquisition_date") or optical_scene_meta.get("date")) if optical_scene_meta else (active_scene_meta.get("acquisition_date") if active_scene_meta else None)
            sar_d = (sar_scene_meta.get("acquisition_date") or sar_scene_meta.get("date")) if sar_scene_meta else None
            trace_start_details = {
                "tool": "optical_sar_analysis",
                "active_pair_id": active_pair_id,
                "optical_scene_id": optical_scene_id or target_id,
                "sar_scene_id": resolved_sar_id,
                "optical_date": opt_d,
                "sar_date": sar_d
            }
        else:
            trace_start_details = {
                "tool": tool_name,
                "intent": intent_name,
                "target_scene_id": target_id,
                "mode": mode
            }

        trace.add_step(
            step="tool_execution",
            status="started",
            details=trace_start_details
        )

        resolved_img_path = current_active_meta.get("image_path") if current_active_meta else None

        exec_res = execute_tool(
            tool_name=tool_name,
            upload_dir=upload_dir,
            output_dir=upload_dir / "multispectral",
            input_result=input_result,
            query=query,
            target_scene_id=target_id,
            before_scene_id=before_scene_id,
            after_scene_id=after_scene_id,
            optical_scene_id=optical_scene_id or target_id,
            sar_scene_id=sar_scene_id or tool_item.get("compatible_sar_scene"),
            image_path=resolved_img_path,
            active_scene=current_active_meta,
            active_pair_id=active_pair_id,
            selected_scene_id=target_id
        )

        if not exec_res.get("success"):
            trace.add_step(
                step="tool_execution",
                status="failed",
                details=exec_res
            )
            continue

        trace_completed_details = {
            "tool": tool_name,
            "target_scene_id": target_id,
            "returned_scene_id": exec_res.get("scene_id", target_id),
            "active_pair_id": active_pair_id if tool_name == "optical_sar_model" else None
        }
        is_vlm_bypassed = (
            tool_name == "remote_sensing_vlm"
            and (exec_res.get("deployment_constrained") or not exec_res.get("vlm_available", True))
        )
        step_status = "bypassed" if is_vlm_bypassed else "completed"

        if exec_res.get("deployment_constrained"):
            trace_completed_details["status"] = "VLM BYPASSED"
            trace_completed_details["vlm_status"] = "offline_low_memory_deployment"
            trace_completed_details["deployment_note"] = (
                "VLM deep inference bypassed on 512 MB Render deployment to prevent out-of-memory crash. "
                "Deterministic scientific tools remain fully functional."
            )
        elif tool_name == "remote_sensing_vlm":
            trace_completed_details["status"] = "VLM EXECUTED"

        trace.add_step(
            step="tool_execution",
            status=step_status,
            details=trace_completed_details
        )

        # Interpret tool output
        comp_interpretation = None
        vlm_synthesis = None
        has_dedicated_vlm = any(t["tool"] == "remote_sensing_vlm" for t in ready_tools)

        from app.tools.vlm_analysis import is_local_vlm_enabled

        if tool_name == "ndvi_analysis":
            wants_visual = any(k in query.lower() for k in ["explain", "describe", "visual", "look", "what it means", "what does this mean", "interpret"])
            if not has_dedicated_vlm and wants_visual and is_local_vlm_enabled():
                try:
                    from app.tools.vlm_analysis import run_vlm_analysis, find_scene_image
                    scene_img = find_scene_image(upload_dir, target_scene_id=target_id)
                    if scene_img:
                        stats = exec_res.get("ndvi_statistics", {})
                        m_ndvi = stats.get("mean_ndvi") if stats.get("mean_ndvi") is not None else stats.get("mean")
                        if m_ndvi is not None:
                            cat = (
                                "dense vegetation canopy" if m_ndvi >= 0.5
                                else ("moderate vegetation" if m_ndvi >= 0.2
                                else "sparse vegetation or mixed surface")
                            )
                            synthesis_prompt = (
                                f"In 1 to 2 concise sentences, describe where vegetation cover is visible in this satellite observation."
                            )
                            vlm_synthesis = run_vlm_analysis(query=synthesis_prompt, image_path=scene_img)
                            exec_res["vlm_synthesis"] = vlm_synthesis
                except Exception:
                    pass
            comp_interpretation = interpret_ndvi_result(exec_res, vlm_synthesis=vlm_synthesis)

        elif tool_name == "change_detection_model":
            if is_local_vlm_enabled():
                try:
                    from app.tools.vlm_analysis import run_vlm_analysis
                    triplet_disk = exec_res.get("evidence", {}).get("triplet_disk_path")
                    stats = exec_res.get("statistics", {})
                    before_d = exec_res.get("before", {}).get("date", "Before")
                    after_d = exec_res.get("after", {}).get("date", "After")
                    dyn = stats.get("dynamic_classification", "Bi-temporal change")
                    m_chg = stats.get("mean_delta_ndvi") if stats.get("mean_delta_ndvi") is not None else stats.get("mean_ndvi_change", 0.0)
                    inc = stats.get("vegetation_gain_percentage") if stats.get("vegetation_gain_percentage") is not None else stats.get("increase_percentage", 0.0)
                    dec = stats.get("vegetation_loss_percentage") if stats.get("vegetation_loss_percentage") is not None else stats.get("decrease_percentage", 0.0)
                    stb = stats.get("stable_percentage", 0.0)

                    change_prompt = (
                        f"Bi-temporal satellite analysis between {before_d} and {after_d} detected {dyn}. "
                        f"In 1 to 2 concise sentences, describe where the vegetation gains and losses visually occurred."
                    )
                    if triplet_disk and Path(triplet_disk).exists():
                        vlm_synthesis = run_vlm_analysis(query=change_prompt, image_path=Path(triplet_disk))
                        exec_res["vlm_synthesis"] = vlm_synthesis
                except Exception:
                    pass
            comp_interpretation = interpret_change_detection_result(exec_res, vlm_synthesis=vlm_synthesis)

        elif tool_name == "spectral_band_analysis":
            if not has_dedicated_vlm and is_local_vlm_enabled():
                try:
                    from app.tools.vlm_analysis import run_vlm_analysis, find_scene_image
                    scene_img = find_scene_image(upload_dir, target_scene_id=target_id)
                    if scene_img:
                        indices = exec_res.get("spectral_indices", {})
                        sig = exec_res.get("spectral_signature_classification", "multispectral terrain")
                        m_ndvi = indices.get("mean_ndvi", 0.0)
                        m_ndwi = indices.get("mean_ndwi", 0.0)
                        synthesis_prompt = (
                            f"In 1 to 2 concise sentences, describe visible water bodies or surface moisture features in this scene."
                        )
                        vlm_synthesis = run_vlm_analysis(query=synthesis_prompt, image_path=scene_img)
                        exec_res["vlm_synthesis"] = vlm_synthesis
                except Exception:
                    pass
            comp_interpretation = interpret_spectral_result(exec_res, vlm_synthesis=vlm_synthesis)

        elif tool_name == "optical_sar_model":
            if is_local_vlm_enabled():
                try:
                    from app.tools.vlm_analysis import run_vlm_analysis
                    comp_disk = exec_res.get("evidence", {}).get("composite_disk_path")
                    fus_m = exec_res.get("fusion_metrics", {})
                    cls_env = fus_m.get("environmental_classification", "multimodal terrain")
                    fusion_prompt = (
                        f"In 1 to 2 concise sentences, summarize the surface features in this optical and radar composite."
                    )
                    if comp_disk and Path(comp_disk).exists():
                        vlm_synthesis = run_vlm_analysis(query=fusion_prompt, image_path=Path(comp_disk))
                        exec_res["vlm_synthesis"] = vlm_synthesis
                except Exception:
                    pass
            comp_interpretation = interpret_optical_sar_result(exec_res, vlm_synthesis=vlm_synthesis)

        elif tool_name == "remote_sensing_vlm":
            comp_interpretation = interpret_vlm_result(exec_res)

        elif tool_name == "scene_metadata_model":
            comp_interpretation = interpret_metadata_result(exec_res)

        elif tool_name == "unsupported_capability_handler":
            comp_interpretation = interpret_unsupported_result(exec_res)

        executed_components.append({
            "intent": intent_name,
            "tool": tool_name,
            "title": tool_item["description"],
            "execution_result": exec_res,
            "interpretation": comp_interpretation or {},
            "evidence": exec_res.get("evidence", {})
        })

    # -----------------------------------------
    # STEP 4 — Result Fusion & Final Answer
    # -----------------------------------------

    trace.add_step(
        step="result_fusion",
        status="started",
        details={
            "executed_count": len(executed_components),
            "blocked_count": len(blocked_tools)
        }
    )

    combined_analysis, combined_interpretation, selected_tools = fuse_multi_intent_results(
        raw_query=query,
        query_result=query_result,
        executed_components=executed_components,
        blocked_components=blocked_tools,
        active_scene_meta=active_scene_meta,
        mode=mode,
        before_scene_id=before_scene_id,
        after_scene_id=after_scene_id
    )

    trace.add_step(
        step="result_fusion",
        status="completed",
        details={
            "executed_tools": selected_tools,
            "confidence": combined_interpretation.get("confidence", {}).get("score")
        }
    )

    trace.complete()

    # Determine primary tool description
    primary_tool = executed_components[0]["tool"] if executed_components else (ready_tools[0]["tool"] if ready_tools else "none")
    primary_tool_desc = executed_components[0]["title"] if executed_components else "Multi-Component Remote Sensing Pipeline"

    # Authoritative source scene metadata
    source_scene_id = active_scene_meta.get("scene_id") if active_scene_meta else scene_id
    source_scene_name = active_scene_meta.get("title") if active_scene_meta else scene_id
    source_sensor = active_scene_meta.get("sensor") if active_scene_meta else None
    source_dates = active_scene_meta.get("acquisition_date") or active_scene_meta.get("date") if active_scene_meta else None
    source_modality = active_scene_meta.get("modality", "optical") if active_scene_meta else "optical"
    source_bands = active_scene_meta.get("bands", []) if active_scene_meta else []

    before_date_val = None
    after_date_val = None

    analyzed_scene = None
    if active_scene_meta:
        is_gen = active_scene_meta.get("is_generic_image", False)
        analyzed_scene = {
            "source_scene_id": source_scene_id,
            "source_scene_name": source_scene_name,
            "source_sensor": source_sensor,
            "source_dates": source_dates,
            "source_modality": source_modality,
            "source_bands": source_bands,
            "scene_id": active_scene_meta.get("scene_id"),
            "title": active_scene_meta.get("title", active_scene_meta.get("scene_id")),
            "satellite": active_scene_meta.get("satellite", "Single RGB Image" if is_gen else "Landsat-9"),
            "sensor": active_scene_meta.get("sensor", "Standard RGB Camera" if is_gen else "Multispectral"),
            "date": active_scene_meta.get("date", active_scene_meta.get("acquisition_date", "Unknown")),
            "acquisition_date": active_scene_meta.get("acquisition_date"),
            "upload_timestamp": active_scene_meta.get("upload_timestamp"),
            "path_row_formatted": active_scene_meta.get("path_row_formatted"),
            "resolution": active_scene_meta.get("resolution", "Not available (Non-georeferenced)" if is_gen else "30 m"),
            "crs": active_scene_meta.get("crs", "Not available" if is_gen else "EPSG:32645"),
            "geospatial_metadata": active_scene_meta.get("geospatial_metadata", "Not available" if is_gen else "GeoTIFF standard"),
            "thumbnail": active_scene_meta.get("thumbnail"),
            "bands": active_scene_meta.get("bands", ["RGB"] if is_gen else []),
            "dimensions": active_scene_meta.get("dimensions"),
            "image_format": active_scene_meta.get("image_format"),
            "channels": active_scene_meta.get("channels"),
            "is_generic_image": is_gen,
            "input_category": active_scene_meta.get("input_category", "single_image_vqa" if is_gen else "single_scene"),
            "mode": mode
        }

    # If change detection was among executed components, augment analyzed_scene
    for c in executed_components:
        if c["tool"] == "change_detection_model":
            analyzed_scene = analyzed_scene or {}
            analyzed_scene["mode"] = "bitemporal"
            analyzed_scene["before"] = c["execution_result"].get("before")
            analyzed_scene["after"] = c["execution_result"].get("after")
            before_date_val = c["execution_result"].get("before", {}).get("date") if isinstance(c["execution_result"].get("before"), dict) else None
            after_date_val = c["execution_result"].get("after", {}).get("date") if isinstance(c["execution_result"].get("after"), dict) else None
            source_scene_id = f"{before_scene_id} -> {after_scene_id}"
            source_scene_name = f"Bi-Temporal Pair: {before_date_val or before_scene_id} -> {after_date_val or after_scene_id}"
            source_dates = f"{before_date_val or 'T1'} -> {after_date_val or 'T2'}"
            source_sensor = "Landsat OLI Bi-Temporal Pair"
            source_modality = "optical (bi-temporal)"
            source_bands = ["B4 (Red)", "B5 (NIR)"]
            analyzed_scene["source_scene_id"] = source_scene_id
            analyzed_scene["source_scene_name"] = source_scene_name
            analyzed_scene["source_sensor"] = source_sensor
            analyzed_scene["source_dates"] = source_dates
            analyzed_scene["source_modality"] = source_modality
            analyzed_scene["source_bands"] = source_bands
            analyzed_scene["before_scene_id"] = before_scene_id
            analyzed_scene["after_scene_id"] = after_scene_id
            analyzed_scene["before_date"] = before_date_val
            analyzed_scene["after_date"] = after_date_val

        if c["tool"] == "optical_sar_model":
            analyzed_scene = analyzed_scene or {}
            analyzed_scene["mode"] = "multimodal_pair"
            resolved_opt_id = (optical_scene_meta.get("scene_id") if optical_scene_meta else None) or optical_scene_id or scene_id
            resolved_sar_id = (sar_scene_meta.get("scene_id") if sar_scene_meta else None) or sar_scene_id or c.get("compatible_sar_scene")
            source_scene_id = f"{resolved_opt_id} + {resolved_sar_id}"
            source_scene_name = f"Optical + SAR Pair: {resolved_opt_id} + {resolved_sar_id}"
            opt_d = (optical_scene_meta.get("acquisition_date") or optical_scene_meta.get("date")) if optical_scene_meta else (active_scene_meta.get("acquisition_date") if active_scene_meta else None)
            sar_d = (sar_scene_meta.get("acquisition_date") or sar_scene_meta.get("date")) if sar_scene_meta else None
            source_dates = f"{opt_d or 'Optical'} + {sar_d or 'SAR'}"
            source_sensor = "Landsat-9 OLI-2 + Sentinel-1 C-SAR"
            source_modality = "optical + sar"
            source_bands = ["B2", "B3", "B4", "B5", "VV", "VH"]
            analyzed_scene["source_scene_id"] = source_scene_id
            analyzed_scene["source_scene_name"] = source_scene_name
            analyzed_scene["source_sensor"] = source_sensor
            analyzed_scene["source_dates"] = source_dates
            analyzed_scene["source_modality"] = source_modality
            analyzed_scene["source_bands"] = source_bands
            analyzed_scene["optical_scene_id"] = resolved_opt_id
            analyzed_scene["sar_scene_id"] = resolved_sar_id
            analyzed_scene["active_pair_id"] = active_pair_id

    return {
        "success": True,
        "query": query,
        "multi_intent": query_result.get("multi_intent", False),
        "intent": query_result.get("primary_intent", query_result.get("intent")),
        "primary_intent": query_result.get("primary_intent", query_result.get("intent")),
        "secondary_intents": query_result.get("secondary_intents", []),
        "intents": query_result.get("intents", []),
        "intent_reason": query_result.get("reason"),
        "selected_tool": primary_tool,
        "selected_tools": selected_tools,
        "tool_description": primary_tool_desc,
        "components": combined_analysis.get("components", []),
        "source_scene_id": source_scene_id,
        "source_scene_name": source_scene_name,
        "source_dates": source_dates,
        "source_sensor": source_sensor,
        "source_modality": source_modality,
        "source_bands": source_bands,
        "before_scene_id": before_scene_id,
        "after_scene_id": after_scene_id,
        "before_date": before_date_val,
        "after_date": after_date_val,
        "analyzed_scene": analyzed_scene,
        "analysis": combined_analysis,
        "interpretation": combined_interpretation,
        "execution_trace": trace.to_dict()
    }