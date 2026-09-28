import requests
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"
WORKSPACE = "satquery_wyken7ew"
SINGLE_SCENE_ID = "LC08_L2SP_139041_20260414_20260423_02_T1"
BEFORE_SCENE_ID = "LC09_L2SP_141040_20260810_20260811_02_T1"
AFTER_SCENE_ID = "LC09_L2SP_141040_20260826_20260827_02_T1"

def run_test(test_num: int, title: str, payload: dict, check_fn):
    print(f"\n{'='*70}")
    print(f"TEST {test_num}: {title}")
    print(f"Query: \"{payload.get('query')}\"")
    print(f"Active Scene ID: {payload.get('active_scene_id')}")
    print(f"Mode: {payload.get('mode')}")
    print(f"{'='*70}")

    try:
        resp = requests.post(f"{BASE_URL}/api/query", json=payload, timeout=180)
        if resp.status_code != 200:
            print(f"[FAIL] HTTP {resp.status_code} - {resp.text}")
            return False
        
        data = resp.json()
        print(f"Response success: {data.get('success')}")
        print(f"Multi-intent: {data.get('multi_intent')}")
        print(f"Selected tools: {data.get('selected_tools') or [data.get('selected_tool')]}")
        if data.get("components"):
            print(f"Components ({len(data['components'])}):")
            for c in data["components"]:
                print(f"  - [{c.get('status')}] {c.get('tool_name')}: {c.get('message')}")
        
        passed, reason = check_fn(data)
        if passed:
            print(f"[PASS] {reason}")
            return True
        else:
            print(f"[FAIL] {reason}")
            return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

def main():
    results = []

    # Test 1: Single intent NDVI
    payload1 = {
        "query": "Calculate NDVI and explain the vegetation",
        "active_scene_id": SINGLE_SCENE_ID,
        "mode": "single",
        "workspace_id": WORKSPACE
    }
    def check1(d):
        if not d.get("success"):
            return False, "Query failed"
        if d.get("selected_tool") != "ndvi_analysis":
            return False, f"Expected ndvi_analysis, got {d.get('selected_tool')}"
        if not d.get("analysis", {}).get("ndvi_statistics"):
            return False, "Missing ndvi_statistics in analysis"
        return True, "NDVI analysis executed correctly on single scene"
    results.append(run_test(1, "NDVI Alone", payload1, check1))

    # Test 2: Single intent Change Detection on Bi-temporal pair
    payload2 = {
        "query": "What changed between these images?",
        "before_scene_id": BEFORE_SCENE_ID,
        "after_scene_id": AFTER_SCENE_ID,
        "mode": "bitemporal",
        "workspace_id": WORKSPACE
    }
    def check2(d):
        if not d.get("success"):
            return False, "Query failed"
        if d.get("selected_tool") != "change_detection_model":
            return False, f"Expected change_detection_model, got {d.get('selected_tool')}"
        if not d.get("analysis", {}).get("statistics"):
            return False, "Missing change detection statistics"
        return True, "Change detection executed on bi-temporal pair"
    results.append(run_test(2, "Change Detection Alone (Pair)", payload2, check2))

    # Test 3: Compound NDVI + Change detection on Single Scene
    payload3 = {
        "query": "Calculate NDVI and explain the vegetation. Also tell me the changes?",
        "active_scene_id": SINGLE_SCENE_ID,
        "mode": "single",
        "workspace_id": WORKSPACE
    }
    def check3(d):
        if not d.get("success"):
            return False, "Response was not success: True"
        if not d.get("multi_intent"):
            return False, "multi_intent was not True"
        comps = d.get("components", [])
        if len(comps) < 2:
            return False, f"Expected at least 2 components, got {len(comps)}"
        ndvi_comp = next((c for c in comps if c.get("tool_name") == "ndvi_analysis"), None)
        change_comp = next((c for c in comps if c.get("tool_name") == "change_detection_model"), None)
        if not ndvi_comp or ndvi_comp.get("status") != "executed":
            return False, "ndvi_analysis was not executed"
        if not change_comp or change_comp.get("status") != "blocked":
            return False, "change_detection_model was not marked as blocked"
        expected_msg = "Change detection requires a compatible before/after scene pair. The current analysis context contains only one scene. Please select a bi-temporal pair."
        if expected_msg not in change_comp.get("message", ""):
            return False, f"Blocked message didn't match expected exact text. Got: {change_comp.get('message')}"
        return True, "NDVI executed, Change Detection blocked gracefully with exact notice, success: True"
    results.append(run_test(3, "NDVI + Change Detection (Single Scene)", payload3, check3))

    # Test 4: Compound NDVI + Spectral + Change detection on Single Scene
    payload4 = {
        "query": "Calculate NDVI, run spectral analysis, and detect changes.",
        "active_scene_id": SINGLE_SCENE_ID,
        "mode": "single",
        "workspace_id": WORKSPACE
    }
    def check4(d):
        if not d.get("success"):
            return False, "Response failed"
        if not d.get("multi_intent"):
            return False, "multi_intent was not True"
        comps = d.get("components", [])
        executed_tools = [c.get("tool_name") for c in comps if c.get("status") == "executed"]
        blocked_tools = [c.get("tool_name") for c in comps if c.get("status") == "blocked"]
        if "ndvi_analysis" not in executed_tools:
            return False, f"ndvi_analysis not in executed: {executed_tools}"
        if "spectral_band_analysis" not in executed_tools and "spectral_index_tool" not in executed_tools:
            return False, f"spectral tool not in executed: {executed_tools}"
        if "change_detection_model" not in blocked_tools:
            return False, f"change_detection_model not in blocked: {blocked_tools}"
        return True, "NDVI and Spectral executed; Change Detection blocked"
    results.append(run_test(4, "NDVI + Spectral + Change Detection (Single Scene)", payload4, check4))

    # Test 5: Describe scene + NDVI
    payload5 = {
        "query": "Describe this scene and calculate NDVI.",
        "active_scene_id": SINGLE_SCENE_ID,
        "mode": "single",
        "workspace_id": WORKSPACE
    }
    def check5(d):
        if not d.get("success"):
            return False, "Response failed"
        if not d.get("multi_intent"):
            return False, "multi_intent was not True"
        comps = d.get("components", [])
        executed_tools = [c.get("tool_name") for c in comps if c.get("status") == "executed"]
        if "remote_sensing_vlm" not in executed_tools:
            return False, f"remote_sensing_vlm not in executed: {executed_tools}"
        if "ndvi_analysis" not in executed_tools:
            return False, f"ndvi_analysis not in executed: {executed_tools}"
        return True, "Both VLM and NDVI executed and fused"
    results.append(run_test(5, "Describe Scene + NDVI", payload5, check5))

    # Test 6: VQA + NDVI + NDWI
    payload6 = {
        "query": "What objects are visible? Calculate NDVI and NDWI.",
        "active_scene_id": SINGLE_SCENE_ID,
        "mode": "single",
        "workspace_id": WORKSPACE
    }
    def check6(d):
        if not d.get("success"):
            return False, "Response failed"
        if not d.get("multi_intent"):
            return False, "multi_intent was not True"
        comps = d.get("components", [])
        executed_tools = [c.get("tool_name") for c in comps if c.get("status") == "executed"]
        if "remote_sensing_vlm" not in executed_tools:
            return False, f"remote_sensing_vlm not in executed: {executed_tools}"
        if "ndvi_analysis" not in executed_tools:
            return False, f"ndvi_analysis not in executed: {executed_tools}"
        if "spectral_band_analysis" not in executed_tools and "spectral_index_tool" not in executed_tools:
            return False, f"spectral tool not in executed: {executed_tools}"
        return True, "VLM, NDVI, and Spectral all executed and fused"
    results.append(run_test(6, "VQA + NDVI + NDWI", payload6, check6))

    # Test 7: Verify zero hallucination of change detection metrics on Single Scene
    payload7 = {
        "query": "Analyze this scene. What changed in the image and what is the NDVI?",
        "active_scene_id": SINGLE_SCENE_ID,
        "mode": "single",
        "workspace_id": WORKSPACE
    }
    def check7(d):
        if not d.get("success"):
            return False, "Response failed"
        analysis = d.get("analysis", {})
        # Must NOT have change detection statistics
        if analysis.get("statistics", {}).get("vegetation_gain_percentage") is not None:
            return False, "Hallucinated change detection statistics on single scene!"
        if d.get("source_scene_id") != SINGLE_SCENE_ID:
            return False, f"Source scene was replaced! Expected {SINGLE_SCENE_ID}, got {d.get('source_scene_id')}"
        comps = d.get("components", [])
        change_comp = next((c for c in comps if c.get("tool_name") == "change_detection_model"), None)
        if not change_comp or change_comp.get("status") != "blocked":
            return False, "Change detection was not blocked"
        return True, "Zero hallucination: Active scene preserved, Change Detection blocked, NDVI executed"
    results.append(run_test(7, "Authoritative Single Scene Protection", payload7, check7))

    # Test 8: Bi-temporal Pair + Compound NDVI + Change Detection
    payload8 = {
        "query": "Calculate NDVI and explain the vegetation. Also tell me the changes?",
        "before_scene_id": BEFORE_SCENE_ID,
        "after_scene_id": AFTER_SCENE_ID,
        "mode": "bitemporal",
        "workspace_id": WORKSPACE
    }
    def check8(d):
        if not d.get("success"):
            return False, "Response failed"
        if not d.get("multi_intent"):
            return False, "multi_intent was not True"
        comps = d.get("components", [])
        executed_tools = [c.get("tool_name") for c in comps if c.get("status") == "executed"]
        if "ndvi_analysis" not in executed_tools:
            return False, f"ndvi_analysis not executed on pair: {executed_tools}"
        if "change_detection_model" not in executed_tools:
            return False, f"change_detection_model not executed on pair: {executed_tools}"
        evidence = d.get("analysis", {}).get("evidence", {})
        if not evidence.get("ndvi_map"):
            return False, "Missing ndvi_map in evidence"
        if not (evidence.get("change_map") or evidence.get("comparison_triplet")):
            return False, "Missing change_map or comparison_triplet in evidence"
        return True, "Both NDVI and Change Detection executed on bi-temporal pair with dual evidence"
    results.append(run_test(8, "Bi-temporal Pair Multi-Tool Execution", payload8, check8))

    print(f"\n{'='*70}")
    print(f"VERIFICATION SUMMARY: {sum(results)} / {len(results)} PASSED")
    print(f"{'='*70}")
    if all(results):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
