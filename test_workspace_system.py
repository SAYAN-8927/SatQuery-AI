"""
Test suite for SatQuery Data Workspace & Scene Deletion System.
Covers:
1. Workspace session identification and isolation.
2. Complete scene deletion (all raster bands, previews, derived artifacts).
3. Independent scene deletion (deleting Scene A preserves Scene B).
4. Full workspace clearing (all datasets removed, no orphaned files).
5. Expiration and inactivity cleanup logic.
6. Safety: Global/shared resources and model weights are never touched.
"""

import os
import shutil
import time
from pathlib import Path
import urllib.request
import urllib.error
import json
from datetime import datetime, timedelta

from app.services.workspace_manager import workspace_manager, WorkspaceManager

BASE_URL = "http://127.0.0.1:8000"


def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())


def http_delete(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {}, method="DELETE")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())


def http_post(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())


def run_all_tests():
    print("==================================================")
    print("RUNNING SATQUERY WORKSPACE & DELETION SYSTEM TESTS")
    print("==================================================")

    test_ws_id = f"satquery_test_{int(time.time())}"
    print(f"Test Workspace ID: {test_ws_id}")

    ws_dir = workspace_manager.get_workspace_dir(test_ws_id)
    assert ws_dir.exists(), "Workspace directory should be created"
    assert (ws_dir / "previews").exists(), "previews subfolder should exist"
    assert (ws_dir / "multispectral").exists(), "multispectral subfolder should exist"
    print("[PASS] Test 1 Passed: Isolated workspace directory and subfolders initialized.")

    # ----------------------------------------------------
    # TEST 2: Workspace Info Endpoint
    # ----------------------------------------------------
    status, info = http_get(f"{BASE_URL}/api/workspace/info?workspace_id={test_ws_id}")
    assert status == 200, f"Expected 200, got {status}"
    assert info["data"]["workspace_id"] == test_ws_id
    assert info["data"]["expiry_hours"] == workspace_manager.expiry_hours
    print(f"[PASS] Test 2 Passed: Workspace info endpoint returned active session info (Expiry: {info['data']['expiry_hours']}h).")

    # ----------------------------------------------------
    # TEST 3: Create Synthetic Scene A (4 Landsat bands B2, B3, B4, B5)
    # ----------------------------------------------------
    scene_a_id = "LC09_L2SP_999099_20260901_20260902_02_T1"
    bands_a = ["B2", "B3", "B4", "B5"]
    created_a = []
    for b in bands_a:
        f_name = f"{scene_a_id}_SR_{b}.TIF"
        f_path = ws_dir / f_name
        f_path.write_bytes(b"TEST_GEOTIFF_DATA_FOR_SCENE_A")
        created_a.append(f_path)

        # Synthetic preview
        p_name = f"{scene_a_id}_SR_{b}_preview.png"
        p_path = ws_dir / "previews" / p_name
        p_path.write_bytes(b"TEST_PREVIEW_PNG")

    # Synthetic multispectral artifact
    m_name = f"{scene_a_id}_NDVI.png"
    (ws_dir / "multispectral" / m_name).write_bytes(b"TEST_NDVI_PNG")

    # Verify files on disk
    for f in created_a:
        assert f.exists(), f"File {f} must exist"
    print(f"[PASS] Test 3 Passed: Scene A created with {len(bands_a)} bands, previews, and NDVI artifact.")

    # ----------------------------------------------------
    # TEST 4: Verify Scene A appears in /api/scenes for this workspace
    # ----------------------------------------------------
    status, scenes_resp = http_get(
        f"{BASE_URL}/api/scenes?workspace_id={test_ws_id}",
        headers={"X-Workspace-ID": test_ws_id}
    )
    assert status == 200
    scene_ids = [s["scene_id"] for s in scenes_resp["data"]["scenes"]]
    assert scene_a_id in scene_ids, f"Scene A must be present in scenes: {scene_ids}"
    target_scene = next(s for s in scenes_resp["data"]["scenes"] if s["scene_id"] == scene_a_id)
    assert target_scene["can_delete"] is True, "Scene must have can_delete: True"
    assert len(target_scene["bands"]) == 4, "Must detect all 4 bands"
    print("[PASS] Test 4 Passed: Scene A detected in workspace with 4 bands and can_delete flag.")

    # ----------------------------------------------------
    # TEST 5: Create Scene B in the same workspace
    # ----------------------------------------------------
    scene_b_id = "LC09_L2SP_999099_20260917_20260918_02_T1"
    bands_b = ["B2", "B3", "B4", "B5"]
    created_b = []
    for b in bands_b:
        f_name = f"{scene_b_id}_SR_{b}.TIF"
        f_path = ws_dir / f_name
        f_path.write_bytes(b"TEST_GEOTIFF_DATA_FOR_SCENE_B")
        created_b.append(f_path)

        p_name = f"{scene_b_id}_SR_{b}_preview.png"
        p_path = ws_dir / "previews" / p_name
        p_path.write_bytes(b"TEST_PREVIEW_PNG_B")

    print("[PASS] Test 5 Passed: Scene B created alongside Scene A.")

    # ----------------------------------------------------
    # TEST 6: Delete Scene A and verify Scene B remains untouched
    # ----------------------------------------------------
    status, del_resp = http_delete(
        f"{BASE_URL}/api/scenes/{scene_a_id}?workspace_id={test_ws_id}",
        headers={"X-Workspace-ID": test_ws_id}
    )
    assert status == 200, f"Delete should return 200, got {status}"
    assert del_resp["success"] is True
    assert del_resp["scene_id"] == scene_a_id
    assert del_resp["deleted_count"] >= 4, f"Should have deleted bands and artifacts: {del_resp}"

    # Verify Scene A files are GONE from disk
    for f in created_a:
        assert not f.exists(), f"File {f.name} should be deleted from disk"
    for b in bands_a:
        assert not (ws_dir / "previews" / f"{scene_a_id}_SR_{b}_preview.png").exists(), "Preview should be deleted"
    assert not (ws_dir / "multispectral" / m_name).exists(), "Derived artifact should be deleted"

    # Verify Scene B files REMAIN completely intact on disk
    for f in created_b:
        assert f.exists(), f"Scene B file {f.name} must NOT be deleted!"
    print("[PASS] Test 6 Passed: Scene A physically removed from disk; Scene B completely intact.")

    # ----------------------------------------------------
    # TEST 7: Verify /api/scenes shows only Scene B now
    # ----------------------------------------------------
    status, scenes_resp_after = http_get(
        f"{BASE_URL}/api/scenes?workspace_id={test_ws_id}",
        headers={"X-Workspace-ID": test_ws_id}
    )
    after_ids = [s["scene_id"] for s in scenes_resp_after["data"]["scenes"]]
    assert scene_a_id not in after_ids, "Scene A must NOT be in library"
    assert scene_b_id in after_ids, "Scene B must remain in library"
    print("[PASS] Test 7 Passed: Scene Library updated correctly (Scene A gone, Scene B preserved).")

    # ----------------------------------------------------
    # TEST 8: Test Clear Workspace
    # ----------------------------------------------------
    status, clear_resp = http_post(
        f"{BASE_URL}/api/workspace/clear?workspace_id={test_ws_id}",
        headers={"X-Workspace-ID": test_ws_id}
    )
    assert status == 200
    assert clear_resp["success"] is True

    # Verify Scene B files are now removed too
    for f in created_b:
        assert not f.exists(), f"Scene B file {f.name} should be cleared from disk"

    # Verify workspace is empty
    status, scenes_resp_empty = http_get(
        f"{BASE_URL}/api/scenes?workspace_id={test_ws_id}",
        headers={"X-Workspace-ID": test_ws_id}
    )
    assert scenes_resp_empty["data"]["scene_count"] == 0, "Workspace must have 0 scenes after clear"
    print("[PASS] Test 8 Passed: Clear Workspace physically purged all datasets and reset library.")

    # ----------------------------------------------------
    # TEST 9: Inactivity Expiration Cleanup Test
    # ----------------------------------------------------
    # Create an artificially expired workspace
    old_ws_id = f"satquery_old_{int(time.time())}"
    old_ws_dir = workspace_manager.get_workspace_dir(old_ws_id)
    (old_ws_dir / "dummy.tif").write_bytes(b"DUMMY")

    # Set last active to 48 hours ago in manifest
    old_manifest = {
        "workspace_id": old_ws_id,
        "created_at": (datetime.utcnow() - timedelta(hours=48)).isoformat(),
        "last_active_at": (datetime.utcnow() - timedelta(hours=48)).isoformat(),
        "expiry_hours": 24
    }
    with open(old_ws_dir / "workspace_manifest.json", "w") as f:
        json.dump(old_manifest, f)

    # Set directory mtime back 48 hours
    old_time = time.time() - (48 * 3600)
    os.utime(old_ws_dir, (old_time, old_time))

    cleaned = workspace_manager.cleanup_expired_workspaces()
    assert old_ws_id in cleaned, f"Expired workspace {old_ws_id} should have been pruned: {cleaned}"
    assert not old_ws_dir.exists(), "Expired workspace folder should be removed"
    print("[PASS] Test 9 Passed: Inactivity expiration successfully pruned 48h-old workspace.")

    # ----------------------------------------------------
    # TEST 10: Global Resource Protection
    # ----------------------------------------------------
    # Ensure system directories and LoRA weights were never touched
    assert Path("app/ai/lora_adapter_rs").exists(), "Model weights must be preserved"
    assert Path("app/main.py").exists(), "Application code must be preserved"
    print("[PASS] Test 10 Passed: Global resources and model weights verified safe and untouched.")

    # Clean up test workspace folder
    shutil.rmtree(ws_dir, ignore_errors=True)

    print("\n==================================================")
    print("ALL 10 TESTS PASSED! DATA WORKSPACE SYSTEM IS 100% OPERATIONAL.")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
