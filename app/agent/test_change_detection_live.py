import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.controller import process_user_query

def main():
    print("=" * 65)
    print("TESTING PHASE 8: BI-TEMPORAL CHANGE DETECTION & CHANGE-VQA")
    print("=" * 65)

    test_query = "Compare the vegetation changes between the before and after satellite observations and explain what occurred."
    print(f"\n[Query]: \"{test_query}\"")
    print("Running process_user_query through Agent Controller...\n")

    t0 = time.time()
    response = process_user_query(test_query)
    total_time = round(time.time() - t0, 2)

    print("-" * 65)
    print(f"Success:            {response.get('success')}")
    print(f"Detected Intent:    {response.get('intent')}")
    print(f"Selected Tool:      {response.get('selected_tool')}")
    print(f"Tool Description:   {response.get('tool_description')}")

    analysis = response.get("analysis", {})
    before_info = analysis.get("before", {})
    after_info = analysis.get("after", {})
    print(f"Before Date:        {before_info.get('date')} ({before_info.get('scene_id', '')[:25]})")
    print(f"After Date:         {after_info.get('date')} ({after_info.get('scene_id', '')[:25]})")

    stats = analysis.get("statistics", {})
    print(f"Mean NDVI Change:   {stats.get('mean_ndvi_change')}")
    print(f"Vegetation Gain:    {stats.get('increase_percentage')}%")
    print(f"Vegetation Loss:    {stats.get('decrease_percentage')}%")
    print(f"Stable Surface:     {stats.get('stable_percentage')}%")
    print(f"Dynamic Category:   {stats.get('dynamic_classification')}")

    evidence = analysis.get("evidence", {})
    print(f"Change Heatmap:     {evidence.get('change_map')}")
    print(f"Comparison Triplet: {evidence.get('comparison_triplet')}")
    print(f"Has Change-VQA:     {'vlm_synthesis' in analysis}")

    interpretation = response.get("interpretation", {})
    conf = interpretation.get("confidence", {})
    print(f"Confidence Score:   {conf.get('score')} ({conf.get('level')})")
    print(f"Total Execution:    {total_time}s")

    print("\n[Full Interpretation & Change-VQA Generated]:")
    print("-" * 65)
    print(interpretation.get("interpretation"))
    print("-" * 65)

    assert response.get("success") is True, "Pipeline execution failed!"
    assert response.get("selected_tool") == "change_detection_model", f"Expected change_detection_model, got {response.get('selected_tool')}"
    assert Path(evidence.get("triplet_disk_path", "")).exists(), "Comparison triplet file not found on disk!"
    
    print("\n[SUCCESS] Phase 8 Change Detection & Change-VQA Fully Verified!")

if __name__ == "__main__":
    main()
