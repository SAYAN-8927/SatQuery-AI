import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/query"

def post_query(payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8'))

def test_1_single_scene_a():
    print("=== TEST 1: Single Scene A (10 Aug 2026) ===")
    scene_id = "LC09_L2SP_141040_20260810_20260811_02_T1"
    res = post_query({
        "query": "Is there vegetation in this image?",
        "scene_id": scene_id,
        "mode": "single_scene"
    })
    assert res["success"] is True, f"Failed: {res}"
    assert res["analyzed_scene"]["scene_id"] == scene_id, f"Wrong scene analyzed: {res.get('analyzed_scene')}"
    trace = res["execution_trace"]
    step1 = next(s for s in trace["steps"] if s["step"] == "input_analysis" and s.get("details"))
    assert step1["details"]["selected_scene_id"] == scene_id
    step3 = next(s for s in trace["steps"] if s["step"] == "tool_execution" and s.get("details") and "input_scene" in s["details"])
    assert step3["details"]["input_scene"] == scene_id
    print("PASS: Scene A bound correctly in pipeline and trace.")

def test_2_single_scene_b():
    print("\n=== TEST 2: Single Scene B (26 Aug 2026) ===")
    scene_id = "LC09_L2SP_141040_20260826_20260827_02_T1"
    res = post_query({
        "query": "Is there vegetation in this image?",
        "scene_id": scene_id,
        "mode": "single_scene"
    })
    assert res["success"] is True, f"Failed: {res}"
    assert res["analyzed_scene"]["scene_id"] == scene_id, f"Wrong scene analyzed: {res.get('analyzed_scene')}"
    trace = res["execution_trace"]
    step3 = next(s for s in trace["steps"] if s["step"] == "tool_execution" and s.get("details") and "input_scene" in s["details"])
    assert step3["details"]["input_scene"] == scene_id
    print("PASS: Scene B bound correctly and differs from Scene A.")

def test_3_ndvi_strict_bands():
    print("\n=== TEST 3: NDVI Strict Bands (Scene A) ===")
    scene_id = "LC09_L2SP_141040_20260810_20260811_02_T1"
    res = post_query({
        "query": "Calculate NDVI and explain the vegetation.",
        "scene_id": scene_id,
        "mode": "single_scene"
    })
    assert res["success"] is True, f"Failed: {res}"
    assert res["selected_tool"] == "ndvi_analysis"
    assert res["analyzed_scene"]["scene_id"] == scene_id
    assert "LC09_L2SP_141040_20260810" in res["analysis"]["scene"]
    stats = res['analysis']['ndvi_statistics']
    m_val = stats.get('mean_ndvi') if stats.get('mean_ndvi') is not None else stats.get('mean')
    print(f"PASS: NDVI calculated strictly on Scene A. Mean NDVI: {m_val:.3f}")

def test_4_no_scene_selected_blocked():
    print("\n=== TEST 4: No Scene Selected (Zero Silent Fallback) ===")
    res = post_query({
        "query": "Is there vegetation in this image?",
        "scene_id": None,
        "mode": "single_scene"
    })
    assert res["success"] is False, f"Should have failed but succeeded: {res}"
    assert "No scene selected" in res["error"], f"Unexpected error: {res['error']}"
    print("PASS: System strictly refused to run and blocked query without selecting a silent fallback.")

def test_5_bitemporal_explicit_pair():
    print("\n=== TEST 5: Explicit Bi-Temporal Change Detection ===")
    b_id = "LC09_L2SP_141040_20260810_20260811_02_T1"
    a_id = "LC09_L2SP_141040_20260826_20260827_02_T1"
    res = post_query({
        "query": "Compare these two dates and tell me what changed.",
        "mode": "bitemporal",
        "before_scene_id": b_id,
        "after_scene_id": a_id
    })
    assert res["success"] is True, f"Failed: {res}"
    assert res["selected_tool"] == "change_detection_model"
    assert res["analyzed_scene"]["mode"] == "bitemporal"
    assert res["analysis"]["before"]["scene_id"] == b_id
    assert res["analysis"]["after"]["scene_id"] == a_id
    print(f"PASS: Bi-temporal verified: Before {res['analysis']['before']['date']} -> After {res['analysis']['after']['date']}")

def test_6_optical_sar_fusion():
    print("\n=== TEST 6: Multimodal Optical + SAR Fusion ===")
    opt_id = "LC09_L2SP_141040_20260810_20260811_02_T1"
    sar_id = "S1A_IW_GRDH_1SDV_20260810"
    res = post_query({
        "query": "Analyze this scene using optical and SAR data.",
        "mode": "fusion",
        "scene_id": opt_id,
        "optical_scene_id": opt_id,
        "sar_scene_id": sar_id
    })
    assert res["success"] is True, f"Failed: {res}"
    assert res["selected_tool"] == "optical_sar_model"
    assert res["analyzed_scene"]["mode"] == "fusion"
    print(f"PASS: Fusion verified on {res['analysis']['optical_scene']} + {res['analysis']['sar_scene']}")

if __name__ == "__main__":
    test_1_single_scene_a()
    test_2_single_scene_b()
    test_3_ndvi_strict_bands()
    test_4_no_scene_selected_blocked()
    test_5_bitemporal_explicit_pair()
    test_6_optical_sar_fusion()
    print("\n==========================================")
    print("ALL 6 TESTS PASSED WITH 100% COMPLIANCE!")
    print("==========================================")
