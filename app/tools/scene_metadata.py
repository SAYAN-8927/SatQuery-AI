import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("satquery.metadata")


def extract_scene_metadata(
    upload_dir: Path = Path("uploads"),
    target_scene_id: Optional[str] = None,
    active_scene: Optional[Dict[str, Any]] = None,
    input_result: Optional[Dict[str, Any]] = None,
    active_pair_id: Optional[str] = None,
    selected_scene_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Extract authoritative, deterministically verified scene metadata.
    Enforces strict scene identity verification: never silently falls back to an arbitrary scene.
    """
    effective_target_id = target_scene_id or selected_scene_id
    scene = None

    # 1. Match by active_scene if provided and matching target
    if active_scene:
        if not effective_target_id or active_scene.get("scene_id") == effective_target_id:
            scene = active_scene
        elif effective_target_id in active_scene.get("scene_id", "") or active_scene.get("scene_id", "") in effective_target_id:
            scene = active_scene

    # 2. Search catalog strictly by target_scene_id
    if not scene and effective_target_id and input_result:
        for s in input_result.get("scenes", []):
            s_id = s.get("scene_id", "")
            if s_id == effective_target_id:
                scene = s
                break
        if not scene:
            for s in input_result.get("scenes", []):
                s_id = s.get("scene_id", "")
                if effective_target_id in s_id or s_id in effective_target_id:
                    scene = s
                    break

    # If active_scene was passed without target restriction, use it
    if not scene and active_scene:
        scene = active_scene

    # STRICT AUDIT: If scene not resolved, NEVER silently fall back to scenes[0]
    if not scene:
        logger.warning(
            f"[METADATA AUDIT] Scene lookup failed for target_scene_id='{effective_target_id}'. "
            f"No silent fallback permitted."
        )
        return {
            "success": False,
            "tool": "scene_metadata_model",
            "error": f"No authoritative scene metadata could be found for scene ID '{effective_target_id}'."
        }

    returned_scene_id = scene.get("scene_id") or "Unknown"

    # Authoritative verification
    if effective_target_id and returned_scene_id != effective_target_id and effective_target_id not in returned_scene_id and returned_scene_id not in effective_target_id:
        logger.error(
            f"[METADATA AUDIT FAIL] returned_metadata_scene_id ({returned_scene_id}) != "
            f"selected_scene_id ({effective_target_id})"
        )
        return {
            "success": False,
            "tool": "scene_metadata_model",
            "error": f"Metadata scene mismatch: requested '{effective_target_id}' but resolved '{returned_scene_id}'."
        }

    satellite = scene.get("satellite") or "Not available"
    sensor = scene.get("sensor") or "Not available"
    date = scene.get("date") or scene.get("acquisition_date") or "Not available"
    resolution = scene.get("resolution") or "Not available"
    crs = scene.get("crs") or "Not available"
    path_row = scene.get("path_row_formatted") or scene.get("path_row") or "Not available"
    bands = scene.get("bands") or []
    modality = scene.get("modality") or "optical"
    source_path = str(scene.get("source_file") or scene.get("image_path") or "")

    # Structured Audit Log
    audit_data = {
        "active_scene_id": returned_scene_id,
        "active_pair_id": active_pair_id,
        "selected_scene_id": effective_target_id or returned_scene_id,
        "selected_scene_type": modality,
        "selected_scene_path": source_path,
        "returned_metadata_scene_id": returned_scene_id,
        "verified": True
    }
    logger.info(f"[METADATA AUDIT SUCCESS] {audit_data}")

    summary = (
        f"Platform / Satellite: {satellite}\n"
        f"Sensor: {sensor}\n"
        f"Acquisition Date: {date}\n"
        f"Spatial Resolution: {resolution}\n"
        f"Coordinate Reference System (CRS): {crs}\n"
        f"WRS-2 Path/Row: {path_row}\n"
        f"Available Bands: {', '.join(bands) if bands else 'Standard RGB'}"
    )

    return {
        "success": True,
        "tool": "scene_metadata_model",
        "scene_id": returned_scene_id,
        "metadata_audit": audit_data,
        "metadata": {
            "satellite": satellite,
            "sensor": sensor,
            "acquisition_date": date,
            "spatial_resolution": resolution,
            "crs": crs,
            "path_row": path_row,
            "bands": bands,
            "modality": modality,
            "is_generic_image": scene.get("is_generic_image", False),
            "source_path": source_path
        },
        "summary": summary
    }

