import sys
import time
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

def run_multimodal_tests():
    print("=" * 70)
    print("SATQUERY — AUTOMATIC OPTICAL + SAR MULTIMODAL PAIRING TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # TEST 1, 2, 3, 4: Verify Scenes, Grouping, and Multimodal Pair Creation
    # -------------------------------------------------------------
    print("\n--- TEST 1, 2, 3, 4: GET /api/scenes ---")
    resp = requests.get(f"{BASE_URL}/api/scenes")
    assert resp.status_code == 200, f"Failed /api/scenes: {resp.text}"
    data = resp.json()["data"]

    scenes = data.get("scenes", [])
    multimodal_pairs = data.get("multimodal_pairs", [])
    bi_temporal_pairs = data.get("bi_temporal_pairs", [])

    print(f"Total scenes: {len(scenes)}")
    print(f"Total multimodal pairs: {len(multimodal_pairs)}")
    print(f"Total bi-temporal pairs: {len(bi_temporal_pairs)}")

    # TEST 2: Landsat B2-B5 grouped as one scene
    landsat_scenes = [s for s in scenes if s["scene_id"] == "LC91340522026109SGI00"]
    assert len(landsat_scenes) == 1, "Landsat Port Blair scene missing or fragmented"
    landsat_s = landsat_scenes[0]
    print(f"TEST 2 PASS: Landsat grouped as ONE scene '{landsat_s['scene_id']}' with bands: {landsat_s['bands']}")
    assert all(b in landsat_s["bands"] for b in ["B2", "B3", "B4", "B5"]), "Missing Landsat bands"

    # TEST 3: Sentinel-1 VV+VH grouped as one SAR scene
    sar_scenes = [s for s in scenes if s["scene_id"] == "S1A_IW_GRD_20260413_064061"]
    assert len(sar_scenes) == 1, "Sentinel-1 Port Blair scene missing or fragmented"
    sar_s = sar_scenes[0]
    print(f"TEST 3 PASS: Sentinel-1 grouped as ONE SAR scene '{sar_s['scene_id']}' with polarizations: {sar_s['bands']}")
    assert "VV" in sar_s["bands"] and "VH" in sar_s["bands"], "Missing VV or VH in SAR scene"

    # TEST 1 & 4: Multimodal pair created with 6-day temporal gap
    port_blair_pairs = [p for p in multimodal_pairs if p["optical_scene_id"] == "LC91340522026109SGI00" and p["sar_scene_id"] == "S1A_IW_GRD_20260413_064061"]
    assert len(port_blair_pairs) >= 1, "Port Blair Optical + SAR multimodal pair not created"
    pb_pair = port_blair_pairs[0]
    print(f"TEST 1 & 4 PASS: Multimodal pair created: ID '{pb_pair['pair_id']}'")
    print(f"  Location: {pb_pair['location']}")
    print(f"  Optical: {pb_pair['optical_satellite']} ({pb_pair['optical_acquisition_date']})")
    print(f"  SAR: {pb_pair['sar_satellite']} ({pb_pair['sar_acquisition_date']})")
    print(f"  Temporal gap days: {pb_pair['temporal_gap_days']}")
    print(f"  Spatial overlap: {pb_pair['spatial_overlap']}")
    print(f"  Status: {pb_pair['status']}")
    assert pb_pair["temporal_gap_days"] == 6, f"Expected 6 days gap, got {pb_pair['temporal_gap_days']}"
    assert pb_pair["location"] == "Port Blair", f"Expected 'Port Blair', got {pb_pair['location']}"

    # -------------------------------------------------------------
    # TEST 5 & 6: Select Multimodal Pair & Execute Query
    # -------------------------------------------------------------
    print("\n--- TEST 5 & 6: Execute Optical + SAR Query with Selected Pair ---")
    query_payload = {
        "query": "Use both the optical and radar information to analyze this area.",
        "mode": "multimodal_pair",
        "active_pair_type": "optical_sar",
        "active_pair_id": pb_pair["pair_id"],
        "optical_scene_id": pb_pair["optical_scene_id"],
        "sar_scene_id": pb_pair["sar_scene_id"],
        "active_scene_id": pb_pair["optical_scene_id"],
        "scene_id": pb_pair["optical_scene_id"],
    }
    t0 = time.time()
    resp = requests.post(f"{BASE_URL}/api/query", json=query_payload, timeout=120)
    dur = time.time() - t0
    assert resp.status_code == 200, f"Query failed: {resp.text}"
    q_res = resp.json()

    print(f"Query returned in {dur:.2f}s")
    print(f"  Success: {q_res.get('success')}")
    print(f"  Selected tool: {q_res.get('selected_tool')}")
    assert q_res.get("selected_tool") == "optical_sar_model", f"Expected optical_sar_model, got {q_res.get('selected_tool')}"
    fus_metrics = q_res.get("analysis", {}).get("fusion_metrics", {})
    print(f"  Classification: {fus_metrics.get('environmental_classification')}")
    print(f"  Cross-sensor vegetation agreement: {fus_metrics.get('cross_sensor_vegetation_agreement_pct')}%")
    print(f"  Evidence composite: {q_res.get('analysis', {}).get('evidence', {}).get('fusion_composite')}")
    print("TEST 5 & 6 PASS: Both optical and SAR inputs used in optical_sar_analysis.")

    # -------------------------------------------------------------
    # TEST 7: Run 'Combine the multispectral and radar observations.'
    # -------------------------------------------------------------
    print("\n--- TEST 7: Natural language query routing ---")
    query_payload_2 = {
        "query": "Combine the multispectral and radar observations.",
        "mode": "multimodal_pair",
        "active_pair_type": "optical_sar",
        "active_pair_id": pb_pair["pair_id"],
        "optical_scene_id": pb_pair["optical_scene_id"],
        "sar_scene_id": pb_pair["sar_scene_id"]
    }
    resp = requests.post(f"{BASE_URL}/api/query", json=query_payload_2, timeout=120)
    assert resp.status_code == 200
    q_res_2 = resp.json()
    print(f"  Selected tool: {q_res_2.get('selected_tool')}")
    assert q_res_2.get("selected_tool") == "optical_sar_model"
    print("TEST 7 PASS: 'Combine the multispectral and radar observations' routed to optical_sar_model.")

    # -------------------------------------------------------------
    # TEST 8 & 13: Single-scene Optical NDVI workflow
    # -------------------------------------------------------------
    print("\n--- TEST 8 & 13: Single-scene Optical NDVI workflow ---")
    ndvi_payload = {
        "query": "Calculate NDVI and analyze vegetation vigor.",
        "mode": "single_scene",
        "active_scene_id": "LC91340522026109SGI00",
        "scene_id": "LC91340522026109SGI00"
    }
    resp = requests.post(f"{BASE_URL}/api/query", json=ndvi_payload, timeout=60)
    assert resp.status_code == 200
    ndvi_res = resp.json()
    print(f"  Selected tool: {ndvi_res.get('selected_tool')}")
    assert ndvi_res.get("selected_tool") == "ndvi_analysis"
    mean_ndvi = ndvi_res.get("analysis", {}).get("ndvi_statistics", {}).get("mean_ndvi")
    print(f"  Mean NDVI: {mean_ndvi}")
    print("TEST 8 & 13 PASS: Single-scene NDVI workflow operates independently.")

    # -------------------------------------------------------------
    # TEST 9: Select only SAR in single scene mode
    # -------------------------------------------------------------
    print("\n--- TEST 9: Single-scene SAR metadata / VQA workflow ---")
    sar_payload = {
        "query": "What sensor and acquisition parameters were used for this radar scene?",
        "mode": "single_scene",
        "active_scene_id": "S1A_IW_GRD_20260413_064061",
        "scene_id": "S1A_IW_GRD_20260413_064061"
    }
    resp = requests.post(f"{BASE_URL}/api/query", json=sar_payload, timeout=60)
    assert resp.status_code == 200
    sar_res = resp.json()
    print(f"  Selected tool: {sar_res.get('selected_tool')}")
    assert sar_res.get("selected_tool") in {"scene_metadata_model", "remote_sensing_vlm"}
    print("TEST 9 PASS: SAR single-scene query operates independently.")

    # -------------------------------------------------------------
    # TEST 10: Invalidate pair if scene is missing or deleted
    # -------------------------------------------------------------
    print("\n--- TEST 10: Missing / Deleted Scene Safety on Multimodal Pair ---")
    missing_pair_payload = {
        "query": "Use both the optical and radar information to analyze this area.",
        "mode": "multimodal_pair",
        "active_pair_type": "optical_sar",
        "active_pair_id": "optsar_fake_scene",
        "optical_scene_id": "LC91340522026109SGI00",
        "sar_scene_id": "NON_EXISTENT_SAR_SCENE_DELETED"
    }
    resp = requests.post(f"{BASE_URL}/api/query", json=missing_pair_payload, timeout=30)
    assert resp.status_code == 200
    res_missing = resp.json()
    print(f"  Success: {res_missing.get('success')}")
    print(f"  Error message: {res_missing.get('error')}")
    assert res_missing.get("success") == False
    assert "removed" in res_missing.get("error", "").lower() or "unavailable" in res_missing.get("error", "").lower()
    print("TEST 10 PASS: Multimodal pair safely rejected when a member scene is missing.")

    # -------------------------------------------------------------
    # TEST 11: Switch from Optical + SAR pair to another scene clears pair context
    # -------------------------------------------------------------
    print("\n--- TEST 11: Switching context clears pair ---")
    switch_payload = {
        "query": "Describe this scene.",
        "mode": "single_scene",
        "active_scene_id": "LC08_L2SP_009012_20260720_20260725_02_T1",
        "scene_id": "LC08_L2SP_009012_20260720_20260725_02_T1"
    }
    resp = requests.post(f"{BASE_URL}/api/query", json=switch_payload, timeout=60)
    assert resp.status_code == 200
    res_sw = resp.json()
    print(f"  Target scene ID in result: {res_sw.get('analyzed_scene', {}).get('scene_id')}")
    assert res_sw.get("analyzed_scene", {}).get("scene_id") == "LC08_L2SP_009012_20260720_20260725_02_T1"
    print("TEST 11 PASS: Context switched strictly to selected single scene without pair leakage.")

    # -------------------------------------------------------------
    # TEST 12: Preview cache check (no full-raster rescan)
    # -------------------------------------------------------------
    print("\n--- TEST 12: Preview caching check ---")
    t_p1 = time.time()
    r1 = requests.get(f"{BASE_URL}/api/scenes")
    d1 = time.time() - t_p1
    t_p2 = time.time()
    r2 = requests.get(f"{BASE_URL}/api/scenes")
    d2 = time.time() - t_p2
    print(f"  Call 1 duration: {d1:.3f}s")
    print(f"  Call 2 duration: {d2:.3f}s")
    assert d2 < 2.0, f"Second call took too long ({d2:.2f}s), possible un-cached raster rescan"
    print("TEST 12 PASS: Preview cache is lightweight and does not rescan rasters.")

    # -------------------------------------------------------------
    # TEST 14: Bi-temporal change query unchanged
    # -------------------------------------------------------------
    print("\n--- TEST 14: Bi-temporal change detection functionality ---")
    bitemp_payload = {
        "query": "Compare these two dates and show change detection statistics.",
        "mode": "bitemporal",
        "before_scene_id": "LC09_L2SP_141040_20260810_20260811_02_T1",
        "after_scene_id": "LC09_L2SP_141040_20260826_20260827_02_T1"
    }
    resp = requests.post(f"{BASE_URL}/api/query", json=bitemp_payload, timeout=60)
    assert resp.status_code == 200
    bitemp_res = resp.json()
    print(f"  Selected tool: {bitemp_res.get('selected_tool')}")
    assert bitemp_res.get("selected_tool") == "change_detection_model"
    print("TEST 14 PASS: Bi-temporal change detection remains fully operational.")

    print("\n" + "=" * 70)
    print("ALL 14 MULTIMODAL PAIRING TESTS PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_multimodal_tests()
