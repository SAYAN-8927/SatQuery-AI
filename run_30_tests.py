import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

OPTICAL_SCENE_1 = "LC09_L2SP_141040_20260810_20260811_02_T1"
OPTICAL_SCENE_2 = "LC09_L2SP_141040_20260826_20260827_02_T1"
PNG_SCENE = "Screenshot_2026-09-20_204539"

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

def run_all_tests():
    results = {}
    print("=" * 70)
    print("STARTING SATQUERY AI 30-TEST BLACK-BOX REGRESSION SUITE")
    print("=" * 70)

    # TEST 1: Explicit NDVI paraphrase
    q1 = "Could you calculate the vegetation index here and briefly interpret what it says about the vegetation?"
    r1 = send_query({"query": q1, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    tool1 = r1.get("selected_tool")
    m1 = get_mean_ndvi(r1)
    has_ndvi1 = tool1 == "ndvi_analysis" or any(c.get("tool") == "ndvi_analysis" for c in r1.get("components", []))
    results[1] = {
        "pass": has_ndvi1 and r1.get("success", False) and m1 is not None,
        "details": f"Tool: {tool1}, Mean NDVI: {m1}"
    }
    print(f"Test 1: {'PASS' if results[1]['pass'] else 'FAIL'} - {results[1]['details']}", flush=True)

    # TEST 2: Quantify vegetation
    q2 = "For the scene I have selected right now, quantify how healthy the vegetation appears and explain the result."
    r2 = send_query({"query": q2, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    m2 = get_mean_ndvi(r2)
    has_ndvi2 = r2.get("selected_tool") == "ndvi_analysis" or any(c.get("tool") == "ndvi_analysis" for c in r2.get("components", []))
    results[2] = {
        "pass": has_ndvi2 and m2 is not None,
        "details": f"Tool: {r2.get('selected_tool')}, Mean NDVI: {m2}"
    }
    print(f"Test 2: {'PASS' if results[2]['pass'] else 'FAIL'} - {results[2]['details']}", flush=True)

    # TEST 3: Vegetation index on active scene
    q3 = "Using only the image currently highlighted in the catalog, what does the vegetation index tell us about this particular acquisition?"
    r3 = send_query({"query": q3, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    results[3] = {
        "pass": r3.get("selected_tool") == "ndvi_analysis" and r3.get("source_scene_id") == OPTICAL_SCENE_2,
        "details": f"Tool: {r3.get('selected_tool')}, Scene: {r3.get('source_scene_id')}"
    }
    print(f"Test 3: {'PASS' if results[3]['pass'] else 'FAIL'} - {results[3]['details']}")

    # TEST 4: Single scene change detection blocked
    q4 = "Tell me what has changed here compared with another observation, if the information needed for that comparison is actually available. Otherwise, tell me exactly what is missing."
    r4 = send_query({"query": q4, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    # Must block change detection cleanly without inventing a pair
    blocked4 = not r4.get("success", True) or any(c.get("status") == "blocked" for c in r4.get("components", [])) or "requires a compatible before/after scene pair" in r4.get("error", "") or "requires a compatible before/after" in str(r4.get("analysis", {}))
    results[4] = {
        "pass": blocked4,
        "details": f"Blocked correctly: {blocked4}, Msg: {r4.get('error') or r4.get('analysis', {}).get('explanation')}"
    }
    print(f"Test 4: {'PASS' if results[4]['pass'] else 'FAIL'} - {results[4]['details']}")

    # TEST 5: Multi-intent: vegetation present + temporal change with 1 scene
    q5 = "First tell me how much vegetation is present, and while you're at it, point out anything that would indicate vegetation has changed over time."
    r5 = send_query({"query": q5, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    comps5 = r5.get("components", [])
    has_exec_ndvi5 = any(c.get("intent") == "vegetation_analysis" and c.get("status") == "executed" for c in comps5)
    has_blocked_change5 = any(c.get("intent") == "change_detection" and c.get("status") == "blocked" for c in comps5)
    results[5] = {
        "pass": has_exec_ndvi5 and has_blocked_change5,
        "details": f"Exec NDVI: {has_exec_ndvi5}, Blocked Change: {has_blocked_change5}"
    }
    print(f"Test 5: {'PASS' if results[5]['pass'] else 'FAIL'} - {results[5]['details']}")

    # TEST 6: Bi-temporal vegetation condition + change detection
    q6 = "Start with the vegetation condition of the current observations, then determine whether the vegetation pattern has shifted between the earlier and later acquisition."
    r6 = send_query({
        "query": q6,
        "mode": "bitemporal",
        "before_scene_id": OPTICAL_SCENE_1,
        "after_scene_id": OPTICAL_SCENE_2
    })
    comps6 = r6.get("components", [])
    has_exec_ndvi6 = any(c.get("intent") == "vegetation_analysis" and c.get("status") == "executed" for c in comps6)
    has_exec_change6 = any(c.get("intent") == "change_detection" and c.get("status") == "executed" for c in comps6)
    results[6] = {
        "pass": has_exec_ndvi6 and has_exec_change6,
        "details": f"Exec NDVI: {has_exec_ndvi6}, Exec Change: {has_exec_change6}"
    }
    print(f"Test 6: {'PASS' if results[6]['pass'] else 'FAIL'} - {results[6]['details']}")

    # TEST 7: Three intents: Visual + Quantify vegetation + Contrast two observations
    q7 = "Give me a quick visual reading of the scene, quantify its vegetation using the appropriate spectral information, and then contrast the two observations for any vegetation-related change."
    r7 = send_query({
        "query": q7,
        "mode": "bitemporal",
        "before_scene_id": OPTICAL_SCENE_1,
        "after_scene_id": OPTICAL_SCENE_2
    })
    comps7 = r7.get("components", [])
    has_vlm7 = any(c.get("intent") == "scene_description" for c in comps7)
    has_ndvi7 = any(c.get("intent") == "vegetation_analysis" for c in comps7)
    has_chg7 = any(c.get("intent") == "change_detection" for c in comps7)
    results[7] = {
        "pass": has_vlm7 and has_ndvi7 and has_chg7,
        "details": f"VLM: {has_vlm7}, NDVI: {has_ndvi7}, Change: {has_chg7}"
    }
    print(f"Test 7: {'PASS' if results[7]['pass'] else 'FAIL'} - {results[7]['details']}")

    # TEST 8: Red and NIR information -> NDVI
    q8 = "Can you use the red and near-infrared information to estimate the relative greenness of the surface and tell me what it means?"
    r8 = send_query({"query": q8, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    results[8] = {
        "pass": r8.get("selected_tool") == "ndvi_analysis",
        "details": f"Tool: {r8.get('selected_tool')}, Intent: {r8.get('intent')}"
    }
    print(f"Test 8: {'PASS' if results[8]['pass'] else 'FAIL'} - {results[8]['details']}")

    # TEST 9: Multispectral measurements -> NDVI/spectral
    q9 = "I don't need a general visual guess. Use the multispectral measurements available in this scene to determine whether vegetation is present and quantify it."
    r9 = send_query({"query": q9, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    results[9] = {
        "pass": r9.get("selected_tool") in {"ndvi_analysis", "spectral_band_analysis"},
        "details": f"Tool: {r9.get('selected_tool')}, Intent: {r9.get('intent')}"
    }
    print(f"Test 9: {'PASS' if results[9]['pass'] else 'FAIL'} - {results[9]['details']}")

    # TEST 10: Forget spectral, looking only at what can be seen -> VLM
    q10 = "Forget spectral calculations. Looking only at what can actually be seen in this picture, is there noticeable plant cover?"
    r10 = send_query({"query": q10, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    results[10] = {
        "pass": r10.get("selected_tool") == "remote_sensing_vlm",
        "details": f"Tool: {r10.get('selected_tool')}, Intent: {r10.get('intent')}"
    }
    print(f"Test 10: {'PASS' if results[10]['pass'] else 'FAIL'} - {results[10]['details']}")

    # TEST 11: Scientific calculation blocked on RGB PNG
    q11 = "Can you derive the vegetation index from the image I just selected and explain the vegetation condition?"
    r11 = send_query({"query": q11, "active_scene_id": PNG_SCENE, "mode": "single_scene"})
    blocked11 = r11.get("analysis", {}).get("scientific_incompatible") is True or "standard RGB" in r11.get("error", "") or "standard RGB" in r11.get("analysis", {}).get("explanation", "")
    results[11] = {
        "pass": blocked11,
        "details": f"Scientific blocked: {blocked11}, Explanation: {r11.get('analysis', {}).get('explanation')}"
    }
    print(f"Test 11: {'PASS' if results[11]['pass'] else 'FAIL'} - {results[11]['details']}")

    # TEST 12: VLM scene description
    q12 = "Pretend you are describing this image to someone who cannot see it. What are the main things visible in the scene?"
    r12 = send_query({"query": q12, "active_scene_id": PNG_SCENE, "mode": "single_scene"})
    results[12] = {
        "pass": r12.get("selected_tool") == "remote_sensing_vlm" and len(r12.get("interpretation", {}).get("interpretation", "")) > 10,
        "details": f"Tool: {r12.get('selected_tool')}, Answer length: {len(r12.get('interpretation', {}).get('interpretation', ''))}"
    }
    print(f"Test 12: {'PASS' if results[12]['pass'] else 'FAIL'} - {results[12]['details']}")

    # TEST 13: Computed vegetation measurement without guessing
    q13 = "Without estimating any numbers yourself, tell me what the computed vegetation measurement says about this landscape."
    r13 = send_query({"query": q13, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    results[13] = {
        "pass": r13.get("selected_tool") == "ndvi_analysis",
        "details": f"Tool: {r13.get('selected_tool')}, Mean NDVI: {r13.get('analysis', {}).get('mean_ndvi')}"
    }
    print(f"Test 13: {'PASS' if results[13]['pass'] else 'FAIL'} - {results[13]['details']}")

    # TEST 14: Increased, decreased, or remained relatively stable -> Change detection
    q14 = "Looking at the earlier and later observations together, where does vegetation appear to have increased, decreased, or remained relatively stable?"
    r14 = send_query({
        "query": q14,
        "mode": "bitemporal",
        "before_scene_id": OPTICAL_SCENE_1,
        "after_scene_id": OPTICAL_SCENE_2
    })
    has_chg14 = r14.get("selected_tool") == "change_detection_model" or any(c.get("tool") == "change_detection_model" for c in r14.get("components", []))
    results[14] = {
        "pass": has_chg14 and r14.get("analysis", {}).get("mean_delta_ndvi") is not None,
        "details": f"Tool: {r14.get('selected_tool')}, Delta NDVI: {r14.get('analysis', {}).get('mean_delta_ndvi')}"
    }
    print(f"Test 14: {'PASS' if results[14]['pass'] else 'FAIL'} - {results[14]['details']}")

    # TEST 15: Different from previous observation
    q15 = "The image is interesting, but I'm more interested in what is different from the previous observation. Can you determine that from what I have selected?"
    r15_single = send_query({"query": q15, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    r15_pair = send_query({"query": q15, "mode": "bitemporal", "before_scene_id": OPTICAL_SCENE_1, "after_scene_id": OPTICAL_SCENE_2})
    p15_single = not r15_single.get("success", True) or "requires a compatible before/after scene pair" in r15_single.get("error", "")
    p15_pair = r15_pair.get("selected_tool") == "change_detection_model" or any(c.get("tool") == "change_detection_model" for c in r15_pair.get("components", []))
    results[15] = {
        "pass": p15_single and p15_pair,
        "details": f"Single blocked: {p15_single}, Pair executed: {p15_pair}"
    }
    print(f"Test 15: {'PASS' if results[15]['pass'] else 'FAIL'} - {results[15]['details']}")

    # TEST 16: Reflected-light + radar -> Optical+SAR
    q16 = "Use both the reflected-light information and the radar observation to give me a combined interpretation of this area."
    r16 = send_query({"query": q16, "active_scene_id": OPTICAL_SCENE_1, "mode": "single_scene"})
    results[16] = {
        "pass": r16.get("selected_tool") == "optical_sar_model",
        "details": f"Tool: {r16.get('selected_tool')}, Classification: {r16.get('analysis', {}).get('fusion_metrics', {}).get('environmental_classification')}"
    }
    print(f"Test 16: {'PASS' if results[16]['pass'] else 'FAIL'} - {results[16]['details']}")

    # TEST 17: Optical + radar perspective
    q17 = "The optical image is useful, but I'd also like the radar perspective included in the same interpretation. Can you do that with what is currently selected?"
    r17 = send_query({"query": q17, "active_scene_id": OPTICAL_SCENE_1, "mode": "single_scene"})
    results[17] = {
        "pass": r17.get("selected_tool") == "optical_sar_model",
        "details": f"Tool: {r17.get('selected_tool')}, Radar Veg Index: {r17.get('analysis', {}).get('sar_metrics', {}).get('mean_rvi')}"
    }
    print(f"Test 17: {'PASS' if results[17]['pass'] else 'FAIL'} - {results[17]['details']}")

    # TEST 18: Blue, green, red, near-infrared spectral request
    q18 = "Compare how the blue, green, red and near-infrared measurements behave across this scene and tell me what that pattern suggests."
    r18 = send_query({"query": q18, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    results[18] = {
        "pass": r18.get("selected_tool") == "spectral_band_analysis",
        "details": f"Tool: {r18.get('selected_tool')}, Sig: {r18.get('analysis', {}).get('spectral_signature_classification')}"
    }
    print(f"Test 18: {'PASS' if results[18]['pass'] else 'FAIL'} - {results[18]['details']}")

    # TEST 19: Green + NIR -> NDWI / surface water
    q19 = "Use the green and near-infrared information to identify surface water in this observation."
    r19 = send_query({"query": q19, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    results[19] = {
        "pass": r19.get("selected_tool") == "spectral_band_analysis",
        "details": f"Tool: {r19.get('selected_tool')}, NDWI: {r19.get('analysis', {}).get('spectral_indices', {}).get('mean_ndwi')}"
    }
    print(f"Test 19: {'PASS' if results[19]['pass'] else 'FAIL'} - {results[19]['details']}")

    # TEST 20: Vegetation condition of later date + meaningful vegetation change
    q20 = "Before you compare the two dates, tell me the vegetation condition of the later observation. After that, explain whether the comparison shows meaningful vegetation change."
    r20 = send_query({
        "query": q20,
        "mode": "bitemporal",
        "before_scene_id": OPTICAL_SCENE_1,
        "after_scene_id": OPTICAL_SCENE_2
    })
    comps20 = r20.get("components", [])
    has_ndvi20 = any(c.get("intent") == "vegetation_analysis" and c.get("status") == "executed" for c in comps20)
    has_chg20 = any(c.get("intent") == "change_detection" and c.get("status") == "executed" for c in comps20)
    results[20] = {
        "pass": has_ndvi20 and has_chg20,
        "details": f"NDVI Exec: {has_ndvi20}, Change Exec: {has_chg20}"
    }
    print(f"Test 20: {'PASS' if results[20]['pass'] else 'FAIL'} - {results[20]['details']}")

    # TEST 21: How green is landscape according to red and NIR + normalized difference
    q21a = "How green is this landscape according to the satellite's red and NIR measurements?"
    r21a = send_query({"query": q21a, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    q21b = "What is the normalized difference between the near-infrared and red response here?"
    r21b = send_query({"query": q21b, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    p21a = r21a.get("selected_tool") == "ndvi_analysis"
    p21b = r21b.get("selected_tool") == "ndvi_analysis"
    results[21] = {
        "pass": p21a and p21b,
        "details": f"21a Tool: {r21a.get('selected_tool')}, 21b Tool: {r21b.get('selected_tool')}"
    }
    print(f"Test 21: {'PASS' if results[21]['pass'] else 'FAIL'} - {results[21]['details']}")

    # TEST 22: Deterministic metadata retrieval
    q22 = "For the observation I have selected, what satellite/sensor, acquisition date and spatial resolution are associated with it?"
    r22 = send_query({"query": q22, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    interp22 = str(r22.get("interpretation", {}).get("interpretation", ""))
    has_sat22 = "Landsat" in interp22
    has_date22 = "26 Aug 2026" in interp22 or "2026" in interp22
    has_res22 = "30 m" in interp22
    results[22] = {
        "pass": r22.get("selected_tool") == "scene_metadata_model" and has_sat22 and has_date22 and has_res22,
        "details": f"Tool: {r22.get('selected_tool')}, Has Landsat: {has_sat22}, Has Date: {has_date22}, Has Res: {has_res22}"
    }
    print(f"Test 22: {'PASS' if results[22]['pass'] else 'FAIL'} - {results[22]['details']}")

    # TEST 23: Deleted/missing scene handling
    q23 = "Run that same analysis again on the image we were just working with."
    r23 = send_query({"query": q23, "active_scene_id": "non_existent_scene_123", "mode": "single_scene"})
    err23 = r23.get("error", "")
    passed23 = not r23.get("success", True) and "removed" in err23
    results[23] = {
        "pass": passed23,
        "details": f"Rejected cleanly: {passed23}, Error msg: {err23}"
    }
    print(f"Test 23: {'PASS' if results[23]['pass'] else 'FAIL'} - {results[23]['details']}")

    # TEST 24: Switching active scenes does not reuse stale result
    q24 = "Can you describe what is visible here?"
    r24_a = send_query({"query": q24, "active_scene_id": PNG_SCENE, "mode": "single_scene"})
    r24_b = send_query({"query": q24, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    scene_a = r24_a.get("source_scene_id")
    scene_b = r24_b.get("source_scene_id")
    results[24] = {
        "pass": scene_a == PNG_SCENE and scene_b == OPTICAL_SCENE_2 and scene_a != scene_b,
        "details": f"Scene A: {scene_a}, Scene B: {scene_b}"
    }
    print(f"Test 24: {'PASS' if results[24]['pass'] else 'FAIL'} - {results[24]['details']}")

    # TEST 25: Switching scene state without full reload
    r25_scenes = urllib.request.urlopen(f"{BASE_URL}/api/scenes").read().decode("utf-8")
    data25 = json.loads(r25_scenes)
    results[25] = {
        "pass": data25.get("success") and len(data25.get("data", {}).get("scenes", [])) >= 5,
        "details": f"Catalog intact with {len(data25.get('data', {}).get('scenes', []))} scenes"
    }
    print(f"Test 25: {'PASS' if results[25]['pass'] else 'FAIL'} - {results[25]['details']}")

    # TEST 26: Duplicate filename upload handling
    # Upload test using multipart form data with same filename but different content
    import io, mimetypes
    boundary = "----SatQueryFormBoundaryXYZ123"
    def make_upload_body(filename: str, content: bytes):
        lines = [
            f"--{boundary}".encode("utf-8"),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode("utf-8"),
            b"Content-Type: image/png",
            b"",
            content,
            f"--{boundary}--".encode("utf-8")
        ]
        return b"\r\n".join(lines)

    content_v1 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    content_v2 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00\x72\xb6\r$\x00\x00\x00\x0bIDATx\x9cc\xf8\x0f\x00\x01\x01\x00\x0c\x00\x03w#n\x10\x00\x00\x00\x00IEND\xaeB`\x82"

    req_up1 = urllib.request.Request(
        f"{BASE_URL}/api/images/upload",
        data=make_upload_body("test_dup.png", content_v1),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    res_up1 = json.loads(urllib.request.urlopen(req_up1).read().decode("utf-8"))

    req_up2 = urllib.request.Request(
        f"{BASE_URL}/api/images/upload",
        data=make_upload_body("test_dup.png", content_v2),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    res_up2 = json.loads(urllib.request.urlopen(req_up2).read().decode("utf-8"))

    fn1 = res_up1.get("filename")
    fn2 = res_up2.get("filename")
    results[26] = {
        "pass": fn1 != fn2 and res_up1.get("success") and res_up2.get("success"),
        "details": f"Upload 1 saved as '{fn1}', Upload 2 saved as '{fn2}' (Coexisting unique identities)"
    }
    print(f"Test 26: {'PASS' if results[26]['pass'] else 'FAIL'} - {results[26]['details']}")

    # TEST 27: "Can you take a look at this?" -> VLM
    q27 = "Can you take a look at this?"
    r27 = send_query({"query": q27, "active_scene_id": PNG_SCENE, "mode": "single_scene"})
    results[27] = {
        "pass": r27.get("selected_tool") == "remote_sensing_vlm",
        "details": f"Tool: {r27.get('selected_tool')}, Intent: {r27.get('intent')}"
    }
    print(f"Test 27: {'PASS' if results[27]['pass'] else 'FAIL'} - {results[27]['details']}")

    # TEST 28: Weather forecasting unsupported query
    q28 = "What will the weather be over this location tomorrow?"
    r28 = send_query({"query": q28, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    interp28 = r28.get("interpretation", {}).get("interpretation", "")
    passed28 = r28.get("selected_tool") == "unsupported_capability_handler" or "not supported" in interp28.lower()
    results[28] = {
        "pass": passed28,
        "details": f"Tool: {r28.get('selected_tool')}, Message: {interp28[:80]}..."
    }
    print(f"Test 28: {'PASS' if results[28]['pass'] else 'FAIL'} - {results[28]['details']}")

    # TEST 29: Calculate vegetation condition
    q29 = "Calculate the vegetation condition of this scene."
    r29 = send_query({"query": q29, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    m29 = get_mean_ndvi(r29)
    results[29] = {
        "pass": r29.get("selected_tool") == "ndvi_analysis" and m29 is not None,
        "details": f"Tool: {r29.get('selected_tool')}, Mean NDVI: {m29}"
    }
    print(f"Test 29: {'PASS' if results[29]['pass'] else 'FAIL'} - {results[29]['details']}", flush=True)

    # TEST 30: Repeated NDVI repeatability & determinism
    q30 = "Calculate NDVI and explain the vegetation."
    r30_a = send_query({"query": q30, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    r30_b = send_query({"query": q30, "active_scene_id": OPTICAL_SCENE_2, "mode": "single_scene"})
    m30_a = get_mean_ndvi(r30_a)
    m30_b = get_mean_ndvi(r30_b)
    results[30] = {
        "pass": m30_a is not None and m30_a == m30_b and r30_a.get("source_scene_id") == r30_b.get("source_scene_id"),
        "details": f"Run 1: {m30_a}, Run 2: {m30_b}, Deterministic match: {m30_a == m30_b}"
    }
    print(f"Test 30: {'PASS' if results[30]['pass'] else 'FAIL'} - {results[30]['details']}", flush=True)

    print("=" * 70)
    passed_count = sum(1 for v in results.values() if v["pass"])
    print(f"FINAL BLACK-BOX TEST SUITE SUMMARY: {passed_count}/30 PASSED")
    print("=" * 70)

    # Save results to json for auditing
    with open("regression_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_all_tests()
