import sys
from pathlib import Path
import json

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.agent.controller import process_user_query
from app.agent.input_analyzer import analyze_input
from app.agent.query_parser import parse_query


def run_all_tests():
    print("=" * 80)
    print("SATQUERY AI: ACTIVE SCENE AUTHORITATIVE VERIFICATION SUITE")
    print("=" * 80)

    # Catalog analysis
    catalog = analyze_input(Path("uploads"))
    scenes = catalog.get("scenes", [])
    print(f"Catalog contains {len(scenes)} scenes.")

    # Locate Landsat-8 scene (Path/Row 139/041 or 009/012)
    lc08_scene = None
    lc09_scene = None
    sar_scene = None

    # Check workspace satquery_wyken7ew for LC08 139/041
    ws_dir = Path("uploads/workspaces/satquery_wyken7ew")
    if ws_dir.exists():
        ws_catalog = analyze_input([ws_dir, Path("uploads")])
        for s in ws_catalog.get("scenes", []):
            if "139041" in s.get("scene_id", ""):
                lc08_scene = s
                break

    if not lc08_scene:
        for s in scenes:
            if s.get("scene_id", "").startswith("LC08"):
                lc08_scene = s
                break

    for s in scenes:
        if s.get("scene_id", "").startswith("LC09"):
            if not lc09_scene:
                lc09_scene = s
        if s.get("modality") == "sar" or s.get("scene_id", "").startswith("S1"):
            if not sar_scene:
                sar_scene = s

    assert lc08_scene is not None, "Landsat-8 scene must exist for testing"
    print(f"Active Landsat-8 Test Scene: {lc08_scene['scene_id']} (Path/Row: {lc08_scene.get('path_row_formatted')})")
    print(f"Catalog SAR Scene: {sar_scene['scene_id'] if sar_scene else 'None'}")

    results = {}

    # -------------------------------------------------------------
    # SPECIFIC REPRODUCTION TEST: The user's exact reported bug
    # Query: "Analyze this scene using optical and SAR data. What changed in the image?"
    # Active: Landsat-8 (14 Apr 2026, Path/Row 139/041)
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[BUG REPRODUCTION TEST] Landsat-8 + 'Analyze this scene using optical and SAR data. What changed in the image?'")
    print("-" * 70)
    r_repro = process_user_query(
        query="Analyze this scene using optical and SAR data. What changed in the image?",
        active_scene_id=lc08_scene["scene_id"],
        scene_id=lc08_scene["scene_id"],
        mode="single_scene",
        workspace_id="satquery_wyken7ew"
    )
    print(f"Success: {r_repro.get('success')}")
    print(f"Intent: {r_repro.get('intent')}")
    print(f"Selected Tool: {r_repro.get('selected_tool')}")
    print(f"Error / Message: {r_repro.get('error')}")

    # Verify intent is optical_sar_analysis, NOT change_detection!
    assert r_repro.get("intent") == "optical_sar_analysis", f"Expected optical_sar_analysis, got {r_repro.get('intent')}"
    # Verify tool was NOT change_detection_model
    assert r_repro.get("selected_tool") != "change_detection_model", "Must NOT select change_detection_model!"
    # Verify it was blocked due to incompatible SAR
    assert r_repro.get("success") is False, "Analysis must be blocked when compatible SAR is missing"
    assert "compatible SAR scene" in r_repro.get("error", ""), f"Unexpected error message: {r_repro.get('error')}"

    # Verify execution trace has active_input_validation
    trace_steps = [s["step"] for s in r_repro.get("execution_trace", {}).get("steps", [])]
    assert "active_input_validation" in trace_steps, f"Trace must contain active_input_validation: {trace_steps}"
    results["Reproduction Test: Bug Fix"] = "PASSED (Intent is optical_sar_analysis, blocked incompatible SAR, did not use 08/10->08/26 pair)"

    # -------------------------------------------------------------
    # TEST A: Select one Landsat scene. Ask NDVI. Must use that exact scene.
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[TEST A] Select one Landsat scene. Ask NDVI. Must use that exact scene.")
    print("-" * 70)
    r_a = process_user_query(
        query="Calculate NDVI and explain the vegetation.",
        active_scene_id=lc08_scene["scene_id"],
        scene_id=lc08_scene["scene_id"],
        mode="single_scene",
        workspace_id="satquery_wyken7ew"
    )
    print(f"Success: {r_a.get('success')}")
    print(f"Intent: {r_a.get('intent')}")
    print(f"Selected Tool: {r_a.get('selected_tool')}")
    print(f"Source Scene ID: {r_a.get('source_scene_id')}")
    print(f"Source Scene Name: {r_a.get('source_scene_name')}")
    assert r_a.get("success") is True, f"Test A failed: {r_a.get('error')}"
    assert r_a.get("selected_tool") == "ndvi_analysis", f"Expected ndvi_analysis, got {r_a.get('selected_tool')}"
    assert r_a.get("source_scene_id") == lc08_scene["scene_id"], f"Expected source_scene_id == {lc08_scene['scene_id']}"
    assert r_a.get("analyzed_scene", {}).get("scene_id") == lc08_scene["scene_id"]
    results["Test A: Active Scene NDVI"] = f"PASSED (Used exact active scene {lc08_scene['scene_id']})"

    # -------------------------------------------------------------
    # TEST B: Select one Landsat scene. Ask scene description. Must use that exact scene.
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[TEST B] Select one Landsat scene. Ask scene description. Must use that exact scene.")
    print("-" * 70)
    r_b = process_user_query(
        query="Describe this scene and what features are present.",
        active_scene_id=lc08_scene["scene_id"],
        scene_id=lc08_scene["scene_id"],
        mode="single_scene",
        workspace_id="satquery_wyken7ew"
    )
    print(f"Success: {r_b.get('success')}")
    print(f"Intent: {r_b.get('intent')}")
    print(f"Selected Tool: {r_b.get('selected_tool')}")
    print(f"Source Scene ID: {r_b.get('source_scene_id')}")
    assert r_b.get("success") is True, f"Test B failed: {r_b.get('error')}"
    assert r_b.get("selected_tool") == "remote_sensing_vlm"
    assert r_b.get("source_scene_id") == lc08_scene["scene_id"]
    results["Test B: Active Scene Description"] = f"PASSED (Used exact active scene {lc08_scene['scene_id']})"

    # -------------------------------------------------------------
    # TEST C: Select one optical scene. Ask optical + SAR.
    # Must require compatible SAR. Must NOT choose unrelated SAR automatically.
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[TEST C] Select one optical scene. Ask optical + SAR.")
    print("-" * 70)
    r_c = process_user_query(
        query="Analyze this scene using optical and SAR data.",
        active_scene_id=lc08_scene["scene_id"],
        scene_id=lc08_scene["scene_id"],
        mode="single_scene",
        workspace_id="satquery_wyken7ew"
    )
    print(f"Success: {r_c.get('success')}")
    print(f"Intent: {r_c.get('intent')}")
    print(f"Selected Tool: {r_c.get('selected_tool')}")
    print(f"Error: {r_c.get('error')}")
    assert r_c.get("success") is False, "Must block execution when compatible SAR is unavailable"
    assert "Optical + SAR analysis requires a compatible SAR scene" in r_c.get("error", "")
    assert r_c.get("source_scene_id") == lc08_scene["scene_id"]
    results["Test C: Optical + SAR Compatibility Gate"] = "PASSED (Required compatible SAR, refused unrelated SAR)"

    # -------------------------------------------------------------
    # TEST D: Select one optical scene. Ask change detection.
    # Must require an explicitly selected compatible before/after pair.
    # Must NOT use a random temporal pair.
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[TEST D] Select one optical scene. Ask change detection.")
    print("-" * 70)
    r_d = process_user_query(
        query="Compare these two dates and tell me what changed.",
        active_scene_id=lc08_scene["scene_id"],
        scene_id=lc08_scene["scene_id"],
        mode="single_scene",
        workspace_id="satquery_wyken7ew"
    )
    print(f"Success: {r_d.get('success')}")
    print(f"Intent: {r_d.get('intent')}")
    print(f"Error: {r_d.get('error')}")
    assert r_d.get("success") is False, "Must block execution when single scene is active without confirmed pair"
    assert "Change detection requires an explicitly selected compatible before/after scene pair" in r_d.get("error", "")
    assert r_d.get("source_scene_id") == lc08_scene["scene_id"]
    results["Test D: Single Scene Change Detection Gate"] = "PASSED (Refused to substitute random temporal pair)"

    # -------------------------------------------------------------
    # TEST E: Explicitly select Aug 10 -> Aug 26 pair. Ask change detection.
    # Must use exactly that pair.
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[TEST E] Explicitly select Aug 10 -> Aug 26 pair. Ask change detection.")
    print("-" * 70)
    pair = catalog.get("bi_temporal_pairs", [None])[0]
    if pair:
        b_id = pair["before"]["scene_id"]
        a_id = pair["after"]["scene_id"]
        r_e = process_user_query(
            query="Compare these two dates and tell me what changed.",
            mode="bitemporal",
            before_scene_id=b_id,
            after_scene_id=a_id
        )
        print(f"Success: {r_e.get('success')}")
        print(f"Intent: {r_e.get('intent')}")
        print(f"Selected Tool: {r_e.get('selected_tool')}")
        print(f"Source Scene Name: {r_e.get('source_scene_name')}")
        assert r_e.get("success") is True, f"Test E failed: {r_e.get('error')}"
        assert r_e.get("selected_tool") == "change_detection_model"
        assert r_e.get("before_scene_id") == b_id
        assert r_e.get("after_scene_id") == a_id
        results["Test E: Explicit Temporal Pair Execution"] = f"PASSED (Executed exactly on {b_id} -> {a_id})"
    else:
        results["Test E: Explicit Temporal Pair Execution"] = "SKIPPED (No bi-temporal pair found in uploads)"

    # -------------------------------------------------------------
    # TEST F: Multiple temporal pairs available. Ask change detection without selecting a pair.
    # Must ask user to select which pair to analyze. Must NOT choose the first pair.
    # -------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[TEST F] Multiple temporal pairs available. Ask change detection without selecting a pair.")
    print("-" * 70)
    # Simulate a catalog with multiple bi-temporal pairs
    mock_multi_pairs_catalog = {
        "scenes": [
            {"scene_id": "LC09_A_20260810", "title": "Pair 1 Scene A"},
            {"scene_id": "LC09_A_20260826", "title": "Pair 1 Scene B"},
            {"scene_id": "LC08_B_20260414", "title": "Pair 2 Scene A"},
            {"scene_id": "LC08_B_20260430", "title": "Pair 2 Scene B"},
        ],
        "bi_temporal_pairs": [
            {"before": {"scene_id": "LC09_A_20260810"}, "after": {"scene_id": "LC09_A_20260826"}},
            {"before": {"scene_id": "LC08_B_20260414"}, "after": {"scene_id": "LC08_B_20260430"}}
        ]
    }
    from app.agent.tool_selector import check_tool_compatibility
    q_meta = parse_query("Compare these two dates and tell me what changed.")
    comp_f = check_tool_compatibility(
        tool_name="change_detection_model",
        input_result=mock_multi_pairs_catalog,
        active_scene=None,
        mode="unselected",
        query_meta=q_meta
    )
    print(f"Compatible: {comp_f.get('compatible')}")
    print(f"Reason: {comp_f.get('reason')}")
    assert comp_f.get("compatible") is False, "Must not be compatible when multiple pairs exist without selection"
    assert "Multiple bi-temporal pairs exist in the catalog" in comp_f.get("reason", "")
    assert "Please select which pair to analyze" in comp_f.get("reason", "")
    results["Test F: Multi-Pair Ambiguity Gate"] = "PASSED (Prompts user to select specific pair, does not pick first pair)"

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    for name, status in results.items():
        print(f"  [PASS] {name}: {status}")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
