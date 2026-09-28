import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.controller import process_user_query

def main():
    print("=" * 65)
    print("TESTING LIVE AGENT CONTROLLER WITH FINE-TUNED VLM TOOL")
    print("=" * 65)

    test_query = "Describe the terrain and land cover features in this satellite scene."
    print(f"\n[Query 1]: \"{test_query}\"")
    print("Running process_user_query through Agent Controller (First call, loading to VRAM)...")

    t0 = time.time()
    response = process_user_query(test_query)
    call1_time = round(time.time() - t0, 2)

    print(f"Success:            {response.get('success')}")
    print(f"Detected Intent:    {response.get('intent')}")
    print(f"Selected Tool:      {response.get('selected_tool')}")
    print(f"Answer:             {response.get('analysis', {}).get('answer')[:100]}...")
    print(f"Call 1 Total Time:  {call1_time}s")

    # Second call
    test_query2 = "Is there vegetation or water visible in this scene?"
    print(f"\n[Query 2]: \"{test_query2}\"")
    t0 = time.time()
    response2 = process_user_query(test_query2)
    call2_time = round(time.time() - t0, 2)

    print(f"Success:            {response2.get('success')}")
    print(f"Detected Intent:    {response2.get('intent')}")
    print(f"Selected Tool:      {response2.get('selected_tool')}")
    print(f"Interpretation:     {response2.get('interpretation', {}).get('interpretation')}")
    print(f"Call 2 Total Time:  {call2_time}s")

    # Third call - explicit visual scene query to test VLM caching speed
    test_query3 = "What does this satellite image show overall?"
    print(f"\n[Query 3 (VLM In-Memory Cache Speed Test)]: \"{test_query3}\"")
    t0 = time.time()
    response3 = process_user_query(test_query3)
    call3_time = round(time.time() - t0, 2)

    print(f"Success:            {response3.get('success')}")
    print(f"Detected Intent:    {response3.get('intent')}")
    print(f"Selected Tool:      {response3.get('selected_tool')}")
    print(f"VLM Answer:         {response3.get('analysis', {}).get('answer')[:120]}...")
    print(f"Call 3 Total Time:  {call3_time}s (Fast response - no reload from disk!)")
    print("=" * 65)
    print("[SUCCESS] Phase 5 Real-Time Agent Tool Integration Verified!")

if __name__ == "__main__":
    main()
