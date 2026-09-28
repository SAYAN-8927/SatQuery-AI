import sys
import os
import json
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.agent.controller import process_user_query
from app.agent.input_analyzer import analyze_input

def run_tests():
    print("=" * 70)
    print("SATQUERY AI: 8-POINT INPUT ROUTING & SINGLE-IMAGE VQA VERIFICATION")
    print("=" * 70)

    # 1. Analyze catalog
    catalog = analyze_input(Path("uploads"))
    print(f"Catalog analyzed: {catalog['scene_count']} scenes, input_type: {catalog['input_type']}")

    png_scene = None
    landsat_scenes = []
    sar_scene = None

    for s in catalog["scenes"]:
        if s.get("is_generic_image"):
            if not png_scene:
                png_scene = s
        elif s.get("modality") == "sar":
            sar_scene = s
        elif s.get("available_analyses", {}).get("ndvi"):
            landsat_scenes.append(s)

    assert png_scene is not None, "A PNG scene (e.g. Screenshot (190).png) must exist in uploads/"
    assert len(landsat_scenes) >= 1, "At least one Landsat scene must exist"

    print(f"\n[TEST ENVIRONMENT CONTEXT]")
    print(f"Selected PNG Scene: '{png_scene['title']}' (ID: {png_scene['scene_id']})")
    print(f"PNG Metadata: Format={png_scene.get('image_format')}, Dims={png_scene.get('dimensions')}, CRS={png_scene.get('crs')}")
    print(f"Selected Landsat Scene: '{landsat_scenes[0]['title']}' (ID: {landsat_scenes[0]['scene_id']})")

    results = {}

    # TEST 1: PNG + "Is there a road?" -> VLM answer
    print("\n--- TEST 1: PNG + 'Is there a road?' ---")
    r1 = process_user_query(
        query="Is there a road in the image?",
        scene_id=png_scene["scene_id"]
    )
    print(f"Success: {r1.get('success')}")
    print(f"Selected Tool: {r1.get('selected_tool')}")
    print(f"Intent: {r1.get('intent')}")
    print(f"Answer: {r1.get('analysis', {}).get('answer', '')[:80]}...")
    assert r1.get("success") is True, f"Test 1 failed: {r1}"
    assert r1.get("selected_tool") == "remote_sensing_vlm", f"Expected remote_sensing_vlm, got {r1.get('selected_tool')}"
    results["Test 1: PNG + Road VQA"] = "PASSED (remote_sensing_vlm answered)"

    # TEST 2: PNG + "Is there vegetation?" -> VLM answer
    print("\n--- TEST 2: PNG + 'Is there vegetation?' ---")
    r2 = process_user_query(
        query="Is there vegetation?",
        scene_id=png_scene["scene_id"]
    )
    print(f"Success: {r2.get('success')}")
    print(f"Selected Tool: {r2.get('selected_tool')}")
    print(f"Intent: {r2.get('intent')}")
    print(f"Answer: {r2.get('analysis', {}).get('answer', '')[:80]}...")
    assert r2.get("success") is True, f"Test 2 failed: {r2}"
    assert r2.get("selected_tool") == "remote_sensing_vlm", f"Expected remote_sensing_vlm, got {r2.get('selected_tool')}"
    results["Test 2: PNG + Vegetation VQA"] = "PASSED (remote_sensing_vlm answered)"

    # TEST 3: PNG + "Is there a water body?" -> VLM answer
    print("\n--- TEST 3: PNG + 'Is there a water body?' ---")
    r3 = process_user_query(
        query="Is there a water body?",
        scene_id=png_scene["scene_id"]
    )
    print(f"Success: {r3.get('success')}")
    print(f"Selected Tool: {r3.get('selected_tool')}")
    print(f"Intent: {r3.get('intent')}")
    print(f"Answer: {r3.get('analysis', {}).get('answer', '')[:80]}...")
    assert r3.get("success") is True, f"Test 3 failed: {r3}"
    assert r3.get("selected_tool") == "remote_sensing_vlm", f"Expected remote_sensing_vlm, got {r3.get('selected_tool')}"
    results["Test 3: PNG + Water Body VQA"] = "PASSED (remote_sensing_vlm answered)"

    # TEST 4: PNG + "Describe the scene." -> VLM scene description
    print("\n--- TEST 4: PNG + 'Describe the scene.' ---")
    r4 = process_user_query(
        query="Describe the scene.",
        scene_id=png_scene["scene_id"]
    )
    print(f"Success: {r4.get('success')}")
    print(f"Selected Tool: {r4.get('selected_tool')}")
    print(f"Intent: {r4.get('intent')}")
    print(f"Answer: {r4.get('analysis', {}).get('answer', '')[:80]}...")
    assert r4.get("success") is True, f"Test 4 failed: {r4}"
    assert r4.get("selected_tool") == "remote_sensing_vlm", f"Expected remote_sensing_vlm, got {r4.get('selected_tool')}"
    results["Test 4: PNG + Describe Scene"] = "PASSED (remote_sensing_vlm scene description)"

    # TEST 5: PNG + "Calculate NDVI." -> Explains Red/NIR spectral bands missing on RGB image
    print("\n--- TEST 5: PNG + 'Calculate NDVI.' ---")
    r5 = process_user_query(
        query="Calculate NDVI.",
        scene_id=png_scene["scene_id"]
    )
    print(f"Success: {r5.get('success')}")
    print(f"Scientific Incompatible: {r5.get('analysis', {}).get('scientific_incompatible')}")
    print(f"Explanation: {r5.get('interpretation', {}).get('summary')}")
    assert r5.get("success") is True, f"Test 5 should return a handled response, got {r5}"
    assert r5.get("analysis", {}).get("scientific_incompatible") is True, "Expected scientific_incompatible flag"
    assert "multispectral" in r5.get("interpretation", {}).get("summary", "").lower() or "red" in r5.get("interpretation", {}).get("summary", "").lower()
    results["Test 5: PNG + Calculate NDVI"] = "PASSED (Explains Red/NIR bands missing on RGB image)"

    # TEST 6: Landsat GeoTIFF + "Calculate NDVI." -> Existing NDVI pipeline
    print("\n--- TEST 6: Landsat GeoTIFF + 'Calculate NDVI.' ---")
    r6 = process_user_query(
        query="Calculate NDVI and explain the vegetation.",
        scene_id=landsat_scenes[0]["scene_id"]
    )
    print(f"Success: {r6.get('success')}")
    print(f"Selected Tool: {r6.get('selected_tool')}")
    print(f"Mean NDVI: {r6.get('analysis', {}).get('ndvi_statistics', {}).get('mean_ndvi')}")
    assert r6.get("success") is True, f"Test 6 failed: {r6}"
    assert r6.get("selected_tool") == "ndvi_analysis", f"Expected ndvi_analysis, got {r6.get('selected_tool')}"
    results["Test 6: Landsat + Calculate NDVI"] = "PASSED (Deterministic NDVI pipeline executed)"

    # TEST 7: Bi-temporal Landsat + "Compare these dates." -> Existing bi-temporal change pipeline
    print("\n--- TEST 7: Bi-temporal Landsat + 'Compare these dates.' ---")
    if len(landsat_scenes) >= 2:
        r7 = process_user_query(
            query="Compare these two dates and tell me what changed.",
            mode="bitemporal",
            before_scene_id=landsat_scenes[0]["scene_id"],
            after_scene_id=landsat_scenes[1]["scene_id"]
        )
        print(f"Success: {r7.get('success')}")
        print(f"Selected Tool: {r7.get('selected_tool')}")
        assert r7.get("success") is True, f"Test 7 failed: {r7}"
        assert r7.get("selected_tool") == "change_detection_model"
        results["Test 7: Bi-Temporal Change Detection"] = "PASSED (Bi-temporal change detection executed)"
    else:
        results["Test 7: Bi-Temporal Change Detection"] = "SKIPPED (<2 Landsat scenes available in uploads)"

    # TEST 8: Optical + SAR -> Existing fusion pipeline
    print("\n--- TEST 8: Optical + SAR + 'Analyze using optical and SAR.' ---")
    if sar_scene:
        r8 = process_user_query(
            query="Analyze this scene using optical and SAR data.",
            mode="fusion",
            scene_id=landsat_scenes[0]["scene_id"],
            optical_scene_id=landsat_scenes[0]["scene_id"],
            sar_scene_id=sar_scene["scene_id"]
        )
        print(f"Success: {r8.get('success')}")
        print(f"Selected Tool: {r8.get('selected_tool')}")
        assert r8.get("success") is True, f"Test 8 failed: {r8}"
        assert r8.get("selected_tool") == "optical_sar_model"
        results["Test 8: Optical + SAR Fusion"] = "PASSED (Cross-sensor optical + SAR fusion executed)"
    else:
        results["Test 8: Optical + SAR Fusion"] = "SKIPPED (No SAR scene found in uploads)"

    print("\n" + "=" * 70)
    print("FINAL TEST RESULTS SUMMARY")
    print("=" * 70)
    for t_name, t_res in results.items():
        print(f"[PASS] {t_name}: {t_res}")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
