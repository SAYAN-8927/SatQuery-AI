from fastapi import APIRouter, UploadFile, File, Form, Header, Query, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import json
import zipfile
from datetime import datetime

from app.services.report_generator import generate_research_report, resolve_evidence_disk_path

from app.services.image_validation import (
    validate_file_extension,
    validate_tiff
)

from app.services.image_classification import classify_image
from app.services.raster_processor import analyze_raster
from app.services.raster_preprocessor import create_preview
from app.services.band_identifier import identify_landsat_band
from app.services.multispectral_processor import process_multispectral_scene
from app.agent.query_parser import parse_query
from app.agent.tool_selector import select_tool
from app.agent.controller import process_user_query
from app.services.workspace_manager import workspace_manager

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/api/images/upload")
async def upload_image(
    file: UploadFile = File(...),
    workspace_id: str | None = Form(None),
    x_workspace_id: str | None = Header(None)
):
    ws_id = workspace_id or x_workspace_id or "satquery_default"
    ws_dir = workspace_manager.get_workspace_dir(ws_id)

    # -----------------------------------------
    # Validate extension
    # -----------------------------------------

    extension_result = validate_file_extension(file.filename)

    if not extension_result["valid"]:
        raise HTTPException(
            status_code=400,
            detail=extension_result["reason"]
        )

    extension = extension_result["extension"]

    # -----------------------------------------
    # Save file to workspace (Unique identity for duplicate filenames)
    # -----------------------------------------
    import hashlib
    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    from app.agent.input_analyzer import LANDSAT_PATTERN
    from app.services.sar_identifier import parse_sar_filename
    sar_info = parse_sar_filename(file.filename)
    is_landsat_or_sar = bool(LANDSAT_PATTERN.match(file.filename)) or bool(sar_info)

    target_filename = file.filename
    file_path = ws_dir / target_filename

    if file_path.exists() and not is_landsat_or_sar:
        try:
            with open(file_path, "rb") as existing_f:
                existing_hash = hashlib.sha256(existing_f.read()).hexdigest()

            if existing_hash != content_hash:
                # Different physical file with duplicate filename: preserve both with unique hash suffix
                stem = Path(file.filename).stem
                suffix = Path(file.filename).suffix
                target_filename = f"{stem}_{content_hash[:8]}{suffix}"
                file_path = ws_dir / target_filename
        except Exception:
            pass

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # Also persist directly into root uploads/ directory so that files are physically
    # present in uploads/ and directly accessible to tools and disk inspectors
    root_upload_file = UPLOAD_DIR / target_filename
    if root_upload_file.resolve() != file_path.resolve():
        try:
            with open(root_upload_file, "wb") as buffer:
                buffer.write(content)
        except Exception:
            pass

    workspace_manager.touch_workspace(ws_id, reset_cleared=True)

    landsat_m = LANDSAT_PATTERN.match(target_filename)
    sar_target_info = parse_sar_filename(target_filename)
    if landsat_m:
        computed_scene_id = landsat_m.group("scene")
    elif sar_target_info:
        computed_scene_id = sar_target_info["scene_id"]
    else:
        import re
        clean_stem = re.sub(r"[^\w\-_]", "_", Path(target_filename).stem).strip("_")
        computed_scene_id = clean_stem or f"IMG_{Path(target_filename).stem}"

    # Preview URL calculation
    preview_url = f"/uploads/{target_filename}"
    if ws_dir.resolve() != UPLOAD_DIR.resolve():
        try:
            rel = file_path.resolve().relative_to(Path("uploads").resolve()).as_posix()
            preview_url = f"/uploads/{rel}"
        except Exception:
            pass

    # -----------------------------------------
    # Basic response
    # -----------------------------------------

    response = {
        "success": True,
        "filename": target_filename,
        "original_filename": file.filename,
        "scene_id": computed_scene_id,
        "content_type": file.content_type,
        "saved_path": str(file_path),
        "workspace_id": ws_id,
        "preview": {
            "preview_url": preview_url
        }
    }

    # -----------------------------------------
    # TIFF validation + metadata
    # -----------------------------------------

    if extension in {".tif", ".tiff"}:

        tiff_result = validate_tiff(file_path)

        if not tiff_result["valid"]:

            file_path.unlink(missing_ok=True)

            raise HTTPException(
                status_code=400,
                detail=tiff_result["reason"]
            )

        response["metadata"] = tiff_result["metadata"]

        # -----------------------------------------
        # Raster analysis
        # -----------------------------------------

        raster_analysis = analyze_raster(file_path)

        response["raster_analysis"] = raster_analysis

        # -----------------------------------------
        # Preview in workspace previews directory
        # -----------------------------------------

        preview_dir = ws_dir / "previews"

        preview_result = create_preview(
            file_path,
            preview_dir
        )

        if preview_result.get("preview_path"):
            try:
                rel = Path(preview_result["preview_path"]).relative_to(Path("uploads")).as_posix()
                preview_result["preview_url"] = f"/uploads/{rel}"
            except Exception:
                pass

        response["preview"] = preview_result

    # -----------------------------------------
    # Image classification
    # -----------------------------------------

    classification = classify_image(
        file.filename,
        response.get("metadata")
    )

    response["classification"] = classification

    # -----------------------------------------
    # Band identification (Optical Landsat or SAR)
    # -----------------------------------------

    if sar_target_info:
        band_information = {
            "identified": True,
            "satellite": sar_target_info.get("satellite", "Sentinel-1A"),
            "band": sar_target_info.get("polarization"),
            "name": f"{sar_target_info.get('polarization')} Polarization",
            "modality": "sar",
            "wavelength_um": "C-Band 5.405 GHz",
            "resolution_m": 10
        }
        response["sar_information"] = sar_target_info
    else:
        band_information = identify_landsat_band(
            file.filename
        )

    response["band_information"] = band_information

    return response


# ==================================================
# MULTISPECTRAL PROCESSING
# ==================================================

@router.post("/api/images/multispectral/process")
async def process_multispectral():

    upload_dir = Path("uploads")

    output_dir = Path("uploads/multispectral")

    result = process_multispectral_scene(
        upload_dir,
        output_dir
    )

    if not result["success"]:

        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )

    return result

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    scene_id: str | None = None
    selected_scene_id: str | None = None
    active_scene_id: str | None = None
    active_scene_files: list[str] | None = None
    selected_scenario: str | None = None
    mode: str | None = "single_scene"
    before_scene_id: str | None = None
    after_scene_id: str | None = None
    optical_scene_id: str | None = None
    sar_scene_id: str | None = None
    active_pair_type: str | None = None
    active_pair_id: str | None = None
    workspace_id: str | None = None


@router.post("/api/query/parse")
async def parse_user_query(request: QueryRequest):

    query_result = parse_query(request.query)

    if not query_result["success"]:
        return query_result

    target_scene_id = request.active_scene_id or request.selected_scene_id or request.scene_id
    tool_result = select_tool(
        query_result["intent"]
    )

    return {
        "success": True,
        "query": request.query,
        "intent": query_result["intent"],
        "intent_reason": query_result["reason"],
        "selected_tool": tool_result["tool"],
        "tool_description": tool_result["description"]
    }


@router.post("/api/query")
async def process_query(
    request: QueryRequest,
    x_workspace_id: str | None = Header(None)
):
    ws_id = request.workspace_id or x_workspace_id
    target_scene_id = request.active_scene_id or request.selected_scene_id or request.scene_id
    return process_user_query(
        query=request.query,
        scene_id=target_scene_id,
        active_scene_id=target_scene_id,
        active_scene_files=request.active_scene_files,
        selected_scenario=request.selected_scenario,
        mode=request.mode or "single_scene",
        before_scene_id=request.before_scene_id,
        after_scene_id=request.after_scene_id,
        optical_scene_id=request.optical_scene_id,
        sar_scene_id=request.sar_scene_id,
        active_pair_type=request.active_pair_type,
        active_pair_id=request.active_pair_id,
        workspace_id=ws_id
    )


@router.get("/api/scenes")
async def get_scenes(
    workspace_id: str | None = Query(None),
    x_workspace_id: str | None = Header(None)
):
    from app.agent.input_analyzer import analyze_input
    ws_id = workspace_id or x_workspace_id or "satquery_default"
    ws_dir = workspace_manager.get_workspace_dir(ws_id)

    # Check if workspace was explicitly cleared
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

    if is_cleared and not has_ws_files:
        return {
            "success": True,
            "data": {
                "file_count": 0,
                "scene_count": 0,
                "input_type": "no_input",
                "files": [],
                "scenes": [],
                "bi_temporal_pairs": [],
                "multimodal_pairs": []
            },
            "workspace_id": ws_id
        }

    search_dirs = [ws_dir]
    if not is_cleared:
        default_ws = workspace_manager.get_workspace_dir("satquery_default")
        if ws_dir.resolve() != default_ws.resolve() and default_ws.exists():
            search_dirs.append(default_ws)
        if Path("uploads").resolve() != ws_dir.resolve():
            search_dirs.append(Path("uploads"))

    analysis = analyze_input(search_dirs)
    return {
        "success": True,
        "data": analysis,
        "workspace_id": ws_id
    }


@router.delete("/api/scenes/{scene_id}")
async def delete_scene_endpoint(
    scene_id: str,
    workspace_id: str | None = Query(None),
    x_workspace_id: str | None = Header(None)
):
    ws_id = workspace_id or x_workspace_id or "satquery_default"
    result = workspace_manager.delete_scene(ws_id, scene_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=404 if "not found" in result.get("error", "").lower() else 400,
            detail=result.get("error", "Failed to delete scene")
        )
    return result


@router.post("/api/workspace/clear")
async def clear_workspace_endpoint(
    workspace_id: str | None = Query(None),
    x_workspace_id: str | None = Header(None)
):
    ws_id = workspace_id or x_workspace_id or "satquery_default"
    result = workspace_manager.clear_workspace(ws_id)

    # Mark cleared flag in manifest
    ws_dir = workspace_manager.get_workspace_dir(ws_id)
    manifest_file = ws_dir / "workspace_manifest.json"
    if manifest_file.exists():
        try:
            with open(manifest_file, "r") as f:
                data = json.load(f)
            data["cleared"] = True
            with open(manifest_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    return result


@router.get("/api/workspace/info")
async def get_workspace_info_endpoint(
    workspace_id: str | None = Query(None),
    x_workspace_id: str | None = Header(None)
):
    ws_id = workspace_id or x_workspace_id or "satquery_default"
    info = workspace_manager.get_workspace_info(ws_id)
    return {
        "success": True,
        "data": info
    }


@router.get("/api/examples")
async def get_example_queries():
    return {
        "success": True,
        "examples": [
            {
                "id": "test-1",
                "label": "Vegetation VQA",
                "icon": "Leaf",
                "query": "Is there vegetation in this image?",
                "description": "Single-image Remote Sensing VQA using fine-tuned SmolVLM-500M + RS LoRA.",
                "badge": "VLM Core"
            },
            {
                "id": "test-2",
                "label": "NDVI Canopy Analysis",
                "icon": "BarChart2",
                "query": "Calculate NDVI and explain the vegetation.",
                "description": "Deterministic Landsat-9 surface reflectance processing + Hybrid VLM synthesis.",
                "badge": "Hybrid Engine"
            },
            {
                "id": "test-3",
                "label": "Bi-Temporal Change",
                "icon": "Clock",
                "query": "Compare these two dates and tell me what changed.",
                "description": "Bi-temporal NDVI delta differencing + 3-panel triplet + VLM-assisted change interpretation.",
                "badge": "Change-VQA"
            },
            {
                "id": "test-4",
                "label": "Spectral Profile",
                "icon": "Activity",
                "query": "Analyze the spectral characteristics of this image.",
                "description": "4-Band signature extraction (B2, B3, B4, B5), NDWI water index, and reflectance chart.",
                "badge": "Multispectral"
            },
            {
                "id": "test-5",
                "label": "Optical + SAR Fusion",
                "icon": "Radio",
                "query": "Analyze this scene using optical and SAR data.",
                "description": "Cross-sensor passive optical (Landsat-9) + active microwave radar (Sentinel-1 C-SAR).",
                "badge": "Multi-Modal"
            }
        ]
    }


# =======================================================================
# SCIENTIFIC RESEARCH REPORT & EVIDENCE DOWNLOAD ENDPOINTS
# =======================================================================

@router.post("/api/report/generate-pdf")
async def generate_analysis_pdf_report(payload: dict):
    """
    Generate a researcher-grade, publication-quality PDF analysis report
    for the supplied analysis result using ReportLab.
    """
    try:
        pdf_path, filename = generate_research_report(payload)
        if not pdf_path.exists():
            raise HTTPException(status_code=500, detail="Report generation failed to produce output file.")

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=filename,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF report generation error: {str(e)}")


@router.post("/api/report/download-evidence-zip")
async def download_evidence_zip_package(payload: dict):
    """
    Bundle generated visual evidence artifacts (figures, triplets, maps)
    into a downloadable ZIP archive for researchers.
    """
    try:
        evidence_dict = payload.get("evidence") or payload.get("analysis", {}).get("evidence") or {}
        if not evidence_dict:
            raise HTTPException(status_code=404, detail="No visual evidence artifacts found for this analysis.")

        reports_dir = Path("uploads/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"SatQuery_Evidence_{ts}.zip"
        zip_path = reports_dir / zip_filename

        added_count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for key, ev_val in evidence_dict.items():
                if isinstance(ev_val, str) and not key.endswith("_disk_path"):
                    disk_p = resolve_evidence_disk_path(ev_val)
                    if disk_p and disk_p.exists():
                        zipf.write(disk_p, arcname=disk_p.name)
                        added_count += 1

        if added_count == 0:
            raise HTTPException(status_code=404, detail="Could not resolve physical evidence files on disk.")

        return FileResponse(
            path=str(zip_path),
            media_type="application/zip",
            filename=zip_filename,
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
                "Cache-Control": "no-cache"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evidence ZIP packaging error: {str(e)}")

    