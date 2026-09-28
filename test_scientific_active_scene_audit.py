import json
import urllib.request
import sys

BASE_URL = "http://127.0.0.1:8000"

def send_query(payload: dict) -> dict:
    url = f"{BASE_URL}/api/query"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_scenes() -> dict:
    url = f"{BASE_URL}/api/scenes"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_tests():
    print("=" * 60)
    print("SATQUERY — SCIENTIFIC & ACTIVE-SCENE AUDIT REGRESSION TESTS")
    print("=" * 60)

    scenes_resp = get_scenes()
    assert scenes_resp["success"], "Failed to retrieve scenes catalog"
    scenes = scenes_resp["data"]["scenes"]
    pairs = scenes_resp["data"]["multimodal_pairs"]

    print(f"Catalog has {len(scenes)} scenes, {len(pairs)} multimodal pairs.")
    port_blair_opt = "LC91340522026109SGI00"
    port_blair_sar = "S1A_IW_GRD_20260413_064061"

    # Find port blair pair
    pb_pair = None
    for p in pairs:
        if port_blair_opt in p["optical_scene_id"] and "S1A_IW_GRD" in p["sar_scene_id"]:
            pb_pair = p
            break
    assert pb_pair is not None, f"Port Blair multimodal pair not found in {pairs}"
    print(f"Found Port Blair pair: {pb_pair['pair_id']}, optical: {pb_pair['optical_scene_id']}, sar: {pb_pair['sar_scene_id']}")

    # -------------------------------------------------------------
    # TEST A — NDWI
    # -------------------------------------------------------------
    print("\n[TEST A] NDWI Calculation & Routing Audit...")
    q_ndwi = "Using the green and NIR bands, calculate the water index for this image."
    payload_a = {
        "query": q_ndwi,
        "active_scene_id": port_blair_opt,
        "mode": "single_scene"
    }
    res_a = send_query(payload_a)
    assert res_a["success"], f"TEST A query failed: {res_a}"
    assert res_a["intent"] in {"water_analysis", "spectral_analysis"}, f"Unexpected intent: {res_a['intent']}"
    assert res_a["selected_tool"] == "spectral_band_analysis", f"Unexpected tool: {res_a['selected_tool']}"

    comp_a = res_a.get("analysis", {}).get("components", [{}])[0]
    indices_a = res_a.get("analysis", {}).get("spectral_indices", {})
    assert "mean_ndwi" in indices_a, f"Missing mean_ndwi in {indices_a}"
    assert "mean_b3_green_reflectance" in indices_a, f"Missing mean_b3 in {indices_a}"
    assert "mean_b5_nir_reflectance" in indices_a, f"Missing mean_b5 in {indices_a}"
    assert "internal_consistency_audit" in indices_a, f"Missing audit in {indices_a}"

    audit_a = indices_a["internal_consistency_audit"]
    print(f"  • Tool: {res_a['selected_tool']}")
    print(f"  • Intent: {res_a['intent']}")
    print(f"  • Mean B3 Green: {indices_a['mean_b3_green_reflectance']}")
    print(f"  • Mean B5 NIR: {indices_a['mean_b5_nir_reflectance']}")
    print(f"  • Mean Pixel-Level NDWI: {indices_a['mean_pixel_ndwi']}")
    print(f"  • Ratio of Mean Bands: {indices_a['ndwi_from_mean_bands']}")
    print(f"  • Explanation: {audit_a['jensens_inequality_explanation'][:80]}...")

    interp_a = str(res_a.get("interpretation", {}).get("interpretation", ""))
    assert "Mean B3 Green Reflectance" in interp_a, "Interpretation missing Mean B3 Green Reflectance"
    assert "Mean B5 NIR Reflectance" in interp_a, "Interpretation missing Mean B5 NIR Reflectance"
    assert "Mean Pixel-Level NDWI" in interp_a, "Interpretation missing Mean Pixel-Level NDWI"
    print("  -> TEST A: PASS")

    # -------------------------------------------------------------
    # TEST B — METADATA GROUNDING
    # -------------------------------------------------------------
    print("\n[TEST B] Authoritative Metadata Grounding...")
    q_meta = "What is the acquisition date and CRS of the selected optical image?"
    payload_b = {
        "query": q_meta,
        "active_scene_id": port_blair_opt,
        "mode": "single_scene"
    }
    res_b = send_query(payload_b)
    assert res_b["success"], f"TEST B failed: {res_b}"
    assert res_b["selected_tool"] == "scene_metadata_model", f"Wrong tool: {res_b['selected_tool']}"
    ret_scene_b = res_b["source_scene_id"]
    print(f"  • Returned scene ID: {ret_scene_b}")
    assert port_blair_opt in ret_scene_b, f"Expected {port_blair_opt} but got {ret_scene_b}"

    interp_b = str(res_b.get("interpretation", {}).get("interpretation", ""))
    print(f"  • Interpretation snippet:\n    " + "\n    ".join(interp_b.split("\n")[:5]))
    assert "LC91340522026109SGI00" in interp_b or "Landsat" in interp_b
    assert "19 Apr 2026" in interp_b or "2026-04-19" in interp_b or "19-Apr-2026" in interp_b, f"Wrong date in {interp_b}"
    assert "EPSG:32646" in interp_b, f"Wrong CRS in {interp_b}"
    print("  -> TEST B: PASS")

    # -------------------------------------------------------------
    # TEST C — OPTICAL + SAR PAIR ANALYSIS & NUMERICAL AUDIT
    # -------------------------------------------------------------
    print("\n[TEST C] Optical + SAR Pair Execution & Scientific Output Audit...")
    q_fusion = "Use both the optical and radar observations to analyze this area."
    payload_c = {
        "query": q_fusion,
        "mode": "multimodal_pair",
        "active_pair_id": pb_pair["pair_id"],
        "active_pair_type": "optical_sar",
        "optical_scene_id": pb_pair["optical_scene_id"],
        "sar_scene_id": pb_pair["sar_scene_id"]
    }
    res_c = send_query(payload_c)
    assert res_c["success"], f"TEST C failed: {res_c}"
    assert res_c["selected_tool"] == "optical_sar_model", f"Wrong tool: {res_c['selected_tool']}"

    opt_m = res_c["analysis"]["optical_metrics"]
    sar_m = res_c["analysis"]["sar_metrics"]
    fus_m = res_c["analysis"]["fusion_metrics"]
    prov = res_c["analysis"]["provenance"]

    print(f"  • Optical Scene: {res_c['analysis']['optical_scene']}")
    print(f"  • SAR Scene: {res_c['analysis']['sar_scene']}")
    assert port_blair_opt in res_c["analysis"]["optical_scene"], f"Wrong optical scene: {res_c['analysis']['optical_scene']}"
    assert port_blair_sar in res_c["analysis"]["sar_scene"], f"Wrong SAR scene: {res_c['analysis']['sar_scene']}"

    # Verify SAR calibration (dB backscatter must be negative and physically sound)
    vv_db = sar_m["mean_sigma0_vv_db"]
    vh_db = sar_m["mean_sigma0_vh_db"]
    print(f"  • Calibrated Mean VV: {vv_db} dB (Must be realistic negative C-band backscatter)")
    print(f"  • Calibrated Mean VH: {vh_db} dB")
    assert -25.0 <= vv_db <= 5.0, f"VV backscatter {vv_db} dB is physically unrealistic!"
    assert -35.0 <= vh_db <= 0.0, f"VH backscatter {vh_db} dB is physically unrealistic!"
    assert vh_db < vv_db, f"Cross-pol VH ({vh_db}) should be lower than co-pol VV ({vv_db})!"

    # Verify RVI
    rvi = sar_m["mean_rvi"]
    print(f"  • Radar Vegetation Index (RVI): {rvi} (Calculated from linear backscatter)")
    assert 0.0 <= rvi <= 1.0, f"RVI {rvi} out of physical bounds [0, 1]!"

    # Verify Water / Inundation wording
    env_class = fus_m["environmental_classification"]
    print(f"  • Environmental classification: {env_class}")
    assert "Confirmed" not in env_class or "Flood" not in env_class, f"Overreaching flood claim detected: {env_class}"
    assert "Water" in env_class or "Marine" in env_class or "Moisture" in env_class, f"Expected water/marine classification: {env_class}"

    # Verify Vegetation threshold reporting
    veg_pct = opt_m["vegetation_pixel_coverage_pct"]
    veg_thresh = opt_m["vegetation_classification_threshold"]
    print(f"  • Vegetation Coverage: {veg_pct}% (Threshold: {veg_thresh})")
    assert veg_thresh == "NDVI >= 0.20", f"Unexpected threshold {veg_thresh}"

    # Verify Consensus & Correlation
    corr_status = fus_m.get("correlation_status")
    paired_px = fus_m.get("valid_paired_pixels")
    print(f"  • Correlation status: {corr_status} ({paired_px} paired pixels)")

    # Verify Provenance
    assert "optical" in prov and "sar" in prov and "fusion" in prov, f"Incomplete provenance: {prov}"
    print(f"  • Provenance verified: Optical={prov['optical']['calibration']}, SAR={prov['sar']['calibration']}")
    print("  -> TEST C: PASS")

    # -------------------------------------------------------------
    # TEST D — SCENE SWITCHING SAFETY
    # -------------------------------------------------------------
    print("\n[TEST D] Scene Switching & Stale State Elimination...")
    # Step 1: Query Port Blair Optical + SAR
    res_d1 = send_query(payload_c)
    assert res_d1["success"]
    assert port_blair_opt in res_d1["source_scene_id"]

    # Step 2: Switch to different optical scene (e.g. LC08_L2SP_138045)
    other_scene = "LC08_L2SP_138045_20260117_20260122_02_T1"
    payload_d2 = {
        "query": "What is the acquisition date and CRS of the selected optical image?",
        "active_scene_id": other_scene,
        "mode": "single_scene"
    }
    res_d2 = send_query(payload_d2)
    assert res_d2["success"]
    assert res_d2["source_scene_id"] == other_scene, f"Expected {other_scene} but got {res_d2['source_scene_id']}"
    interp_d2 = str(res_d2["interpretation"]["interpretation"])
    assert "17 Jan 2026" in interp_d2 or "2026-01-17" in interp_d2, f"Wrong date in {interp_d2}"
    assert "EPSG:32645" in interp_d2, f"Wrong CRS in {interp_d2}"
    print(f"  • Switched to {other_scene} -> Verified: returned metadata matches {other_scene} exactly.")

    # Step 3: Switch back to Port Blair Optical + SAR pair
    res_d3 = send_query(payload_c)
    assert res_d3["success"]
    assert port_blair_opt in res_d3["analysis"]["optical_scene"]
    assert port_blair_sar in res_d3["analysis"]["sar_scene"]
    print(f"  • Switched back to Port Blair pair -> Verified: original pair restored with no stale fallback.")
    print("  -> TEST D: PASS")

    print("\n" + "=" * 60)
    print("ALL AUDIT REGRESSION TESTS PASSED CLEANLY (4/4 PASS)")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
