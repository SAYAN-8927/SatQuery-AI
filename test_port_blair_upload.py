import os
import sys
import json
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
PORT_BLAIR_DIR = Path(r"D:\SIH PROJECT\SATELLITE IMG\port blair\optical image")

def upload_file(file_path: Path, workspace_id: str = "satquery_test_port_blair"):
    boundary = "----WebKitFormBoundaryPortBlairTest7MA4YWxkTrZu0gW"
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = b"\r\n".join([
        f"--{boundary}".encode("utf-8"),
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"'.encode("utf-8"),
        b"Content-Type: image/tiff",
        b"",
        file_bytes,
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="workspace_id"',
        b"",
        workspace_id.encode("utf-8"),
        f"--{boundary}--".encode("utf-8")
    ])

    req = urllib.request.Request(
        f"{BASE_URL}/api/images/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def send_query(payload: dict) -> dict:
    url = f"{BASE_URL}/api/query"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_mean_ndvi(r: dict):
    if not r:
        return None
    an = r.get("analysis", {})
    if an.get("mean_ndvi") is not None:
        return an.get("mean_ndvi")
    stats = an.get("ndvi_statistics", {}) or an.get("statistics", {})
    return stats.get("mean_ndvi") if stats.get("mean_ndvi") is not None else stats.get("mean")

def get_scenes(workspace_id: str = "satquery_test_port_blair"):
    url = f"{BASE_URL}/api/scenes?workspace_id={workspace_id}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_tests():
    print("=" * 70)
    print("TESTING PORT BLAIR LANDSAT-9 UPLOAD & MULTISPECTRAL INTEGRATION")
    print("=" * 70)

    ws_id = "satquery_test_port_blair"

    # Clean test workspace and root uploads before test
    import shutil
    ws_path = Path("uploads/workspaces") / ws_id
    if ws_path.exists():
        shutil.rmtree(ws_path, ignore_errors=True)
    for b in ["B2", "B3", "B4", "B5"]:
        (Path("uploads") / f"LC91340522026109SGI00_{b}.TIF").unlink(missing_ok=True)

    # Step 1: Upload B2
    b2_file = PORT_BLAIR_DIR / "LC91340522026109SGI00_B2.TIF"
    print(f"\n[1] Uploading B2: {b2_file.name} ...")
    res_b2 = upload_file(b2_file, workspace_id=ws_id)
    print("Upload Response for B2:")
    print("  - success:", res_b2.get("success"))
    print("  - scene_id:", res_b2.get("scene_id"))
    print("  - classification:", res_b2.get("classification"))
    print("  - band_information:", res_b2.get("band_information"))

    assert res_b2.get("success") is True, "B2 upload failed"
    assert res_b2.get("scene_id") == "LC91340522026109SGI00", f"Unexpected scene_id: {res_b2.get('scene_id')}"
    assert res_b2.get("classification", {}).get("type") == "remote_sensing", "Not classified as remote_sensing"
    assert res_b2.get("classification", {}).get("modality") == "optical", "Not optical modality"
    assert res_b2.get("classification", {}).get("satellite") == "Landsat-9", "Not identified as Landsat-9"
    assert res_b2.get("band_information", {}).get("identified") is True, "Band not identified"
    assert res_b2.get("band_information", {}).get("band") == "B2", "Band code not B2"
    print(">>> PASS: B2 accepted and correctly classified as Landsat-9 single-band remote-sensing GeoTIFF!")

    # Check Catalog with only B2 uploaded
    scenes_res = get_scenes(workspace_id=ws_id)
    pb_scene = next((s for s in scenes_res["data"]["scenes"] if s["scene_id"] == "LC91340522026109SGI00"), None)
    print("\nCatalog state with only B2 uploaded:")
    print("  - Found scene:", pb_scene is not None)
    if pb_scene:
        print("  - title:", pb_scene.get("title"))
        print("  - satellite:", pb_scene.get("satellite"))
        print("  - sensor:", pb_scene.get("sensor"))
        print("  - crs:", pb_scene.get("crs"))
        print("  - resolution:", pb_scene.get("resolution"))
        print("  - bands:", pb_scene.get("bands"))
        print("  - is_generic_image:", pb_scene.get("is_generic_image"))
        print("  - available_analyses:", pb_scene.get("available_analyses"))
        assert pb_scene.get("satellite") == "Landsat-9"
        assert pb_scene.get("sensor") == "OLI-2 (Operational Land Imager 2)"
        assert pb_scene.get("crs") == "EPSG:32646"
        assert pb_scene.get("resolution") == "30 m"
        assert pb_scene.get("bands") == ["B2"]
        assert pb_scene.get("is_generic_image") is not True, "Should NOT be generic image!"
        assert pb_scene.get("available_analyses", {}).get("ndvi") is False, "NDVI should be False until B4/B5 are uploaded"

    # Step 2: Upload B3, B4, B5
    for band_code in ["B3", "B4", "B5"]:
        f = PORT_BLAIR_DIR / f"LC91340522026109SGI00_{band_code}.TIF"
        print(f"\n[2] Uploading {band_code}: {f.name} ...")
        res_b = upload_file(f, workspace_id=ws_id)
        assert res_b.get("success") is True, f"{band_code} upload failed"
        assert res_b.get("scene_id") == "LC91340522026109SGI00"
        assert res_b.get("band_information", {}).get("band") == band_code
        print(f"  -> {band_code} uploaded successfully!")

    # Step 3: Check that all 4 bands are associated into ONE scene
    print("\n[3] Checking associated scene in Sensor Catalog:")
    scenes_res = get_scenes(workspace_id=ws_id)
    pb_scene = next((s for s in scenes_res["data"]["scenes"] if s["scene_id"] == "LC91340522026109SGI00"), None)
    assert pb_scene is not None, "Port Blair scene missing from catalog"
    print("  - scene_id:", pb_scene.get("scene_id"))
    print("  - title:", pb_scene.get("title"))
    print("  - bands:", pb_scene.get("bands"))
    print("  - file_count:", pb_scene.get("file_count"))
    print("  - available_analyses:", pb_scene.get("available_analyses"))

    assert set(pb_scene.get("bands", [])) == {"B2", "B3", "B4", "B5"}, f"Bands incomplete: {pb_scene.get('bands')}"
    assert pb_scene.get("file_count") == 4, f"Expected 4 files, got {pb_scene.get('file_count')}"
    assert pb_scene.get("available_analyses", {}).get("ndvi") is True, "NDVI should be True"
    assert pb_scene.get("available_analyses", {}).get("multispectral") is True, "Multispectral should be True"
    print(">>> PASS: All four bands successfully associated into one Landsat multispectral scene!")

    # Step 4: Run NDVI analysis query on Port Blair scene
    print("\n[4] Running NDVI Query on Port Blair Scene:")
    q_ndvi = {
        "query": "Calculate the vegetation index (NDVI) for this scene.",
        "active_scene_id": "LC91340522026109SGI00",
        "mode": "single_scene",
        "workspace_id": ws_id
    }
    r_ndvi = send_query(q_ndvi)
    print("  - selected_tool:", r_ndvi.get("selected_tool"))
    print("  - source_scene_id:", r_ndvi.get("source_scene_id"))
    print("  - status:", r_ndvi.get("status"))
    m_ndvi = get_mean_ndvi(r_ndvi)
    print("  - mean_ndvi:", m_ndvi)
    assert r_ndvi.get("selected_tool") == "ndvi_analysis", f"Expected ndvi_analysis, got {r_ndvi.get('selected_tool')}"
    assert r_ndvi.get("source_scene_id") == "LC91340522026109SGI00", "Scene substitution occurred!"
    assert m_ndvi is not None, "NDVI mean is None"
    print(">>> PASS: NDVI calculation completed with NO scene substitution!")

    # Step 5: Run Spectral Band Analysis on Port Blair scene
    print("\n[5] Running Spectral Band Analysis Query on Port Blair Scene:")
    q_spec = {
        "query": "Analyze the spectral signature and band reflectance across all bands.",
        "active_scene_id": "LC91340522026109SGI00",
        "mode": "single_scene",
        "workspace_id": ws_id
    }
    r_spec = send_query(q_spec)
    print("  - selected_tool:", r_spec.get("selected_tool"))
    print("  - source_scene_id:", r_spec.get("source_scene_id"))
    raw_spec = r_spec.get("tool_execution", {}).get("raw_result", {})
    print("  - spectral signature:", raw_spec.get("spectral_signature_classification"))
    print("  - spectral chart:", raw_spec.get("evidence", {}).get("spectral_profile_chart"))

    assert r_spec.get("selected_tool") == "spectral_band_analysis", f"Expected spectral_band_analysis, got {r_spec.get('selected_tool')}"
    assert r_spec.get("source_scene_id") == "LC91340522026109SGI00", "Scene substitution occurred!"
    print(">>> PASS: Spectral band analysis completed with NO scene substitution!")

    # Step 6: Test existing RGB PNG VQA query
    print("\n[6] Testing existing PNG/JPEG VQA query on Screenshot_2026-09-20_204539:")
    q_vlm = {
        "query": "Can you describe what is visible here?",
        "active_scene_id": "Screenshot_2026-09-20_204539",
        "mode": "single_scene",
        "workspace_id": ws_id
    }
    r_vlm = send_query(q_vlm)
    print("  - selected_tool:", r_vlm.get("selected_tool"))
    print("  - source_scene_id:", r_vlm.get("source_scene_id"))
    assert r_vlm.get("selected_tool") == "remote_sensing_vlm"
    assert r_vlm.get("source_scene_id") == "Screenshot_2026-09-20_204539"

    # Step 7: Test scientific block on RGB PNG
    print("\n[7] Testing scientific calculation block on Screenshot_2026-09-20_204539:")
    q_sci_block = {
        "query": "Calculate NDVI for this screenshot.",
        "active_scene_id": "Screenshot_2026-09-20_204539",
        "mode": "single_scene",
        "workspace_id": ws_id
    }
    r_sci_block = send_query(q_sci_block)
    explanation = r_sci_block.get("analysis", {}).get("explanation", "") or r_sci_block.get("error", "")
    print("  - response status:", r_sci_block.get("status"))
    print("  - explanation snippet:", explanation[:100], "...")
    assert "scientific calculations cannot be performed on standard rgb images" in explanation.lower() or r_sci_block.get("analysis", {}).get("scientific_incompatible") is True
    print(">>> PASS: Existing PNG/JPEG VQA and scientific guardrails strictly preserved!")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
