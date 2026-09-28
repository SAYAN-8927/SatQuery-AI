import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.controller import process_user_query

def main():
    print("=" * 65)
    print("TESTING PHASE 6: SMART QUERY ROUTING & HYBRID COOPERATION")
    print("=" * 65)

    # 1. Visual Question (should call VLM)
    q1 = "Is there vegetation in this scene?"
    print(f"\n[Test 1 - Visual Question]: \"{q1}\"")
    r1 = process_user_query(q1)
    print(f"Intent:         {r1.get('intent')}")
    print(f"Selected Tool:  {r1.get('selected_tool')}")
    print(f"Answer:         {r1.get('interpretation', {}).get('interpretation')[:120]}...")
    assert r1.get('selected_tool') == 'remote_sensing_vlm', f"Expected remote_sensing_vlm, got {r1.get('selected_tool')}"
    print("[PASS] Visual question routed to VLM!")

    # 2. Hybrid Calculation Query (should compute NDVI math AND synthesize with VLM)
    q2 = "Analyze the vegetation and calculate NDVI for this scene."
    print(f"\n[Test 2 - Analytical Query]: \"{q2}\"")
    r2 = process_user_query(q2)
    print(f"Intent:         {r2.get('intent')}")
    print(f"Selected Tool:  {r2.get('selected_tool')}")
    analysis = r2.get('analysis', {})
    stats = analysis.get('ndvi_statistics', {})
    m_val = stats.get('mean_ndvi') if stats.get('mean_ndvi') is not None else stats.get('mean')
    print(f"Calculated Mean NDVI: {m_val}")
    print(f"NDVI Map:             {analysis.get('evidence', {}).get('ndvi_map')}")
    print(f"Has VLM Synthesis:    {'vlm_synthesis' in analysis}")
    print("\nFull Interpretation:")
    print("-" * 50)
    print(r2.get('interpretation', {}).get('interpretation'))
    print("-" * 50)
    assert r2.get('selected_tool') == 'ndvi_analysis', f"Expected ndvi_analysis, got {r2.get('selected_tool')}"
    assert 'vlm_synthesis' in analysis, "Expected VLM synthesis in analysis!"
    print("\n[SUCCESS] Phase 6 Smart Query Understanding & Hybrid Synthesis Verified!")

if __name__ == "__main__":
    main()
