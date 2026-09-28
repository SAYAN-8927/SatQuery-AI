import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app

def main():
    print("=" * 65)
    print("TESTING FASTAPI /api/query LIVE WITH FINE-TUNED VLM")
    print("=" * 65)

    client = TestClient(app)

    payload = {
        "query": "Describe what you see in this satellite image."
    }

    print(f"\nSending POST /api/query: {payload['query']}")
    t0 = time.time()
    response = client.post("/api/query", json=payload)
    dt = round(time.time() - t0, 2)

    print(f"HTTP Status Code:    {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"Success:             {data.get('success')}")
    print(f"Detected Intent:     {data.get('intent')}")
    print(f"Selected Tool:       {data.get('selected_tool')}")
    print(f"Tool Description:    {data.get('tool_description')}")
    print(f"Answer:              {data.get('interpretation', {}).get('interpretation')[:150]}...")
    
    meta = data.get("analysis", {}).get("model_metadata", {})
    print(f"Active Adapter:      {meta.get('adapter_path')}")
    print(f"Device:              {meta.get('device')}")
    print(f"Latency:             {meta.get('latency_seconds')}s")
    print(f"Total Request Time:  {dt}s")
    print(f"Trace Steps:         {len(data.get('execution_trace', {}).get('steps', []))} steps logged")
    print("=" * 65)
    print("[SUCCESS] FastAPI /api/query Live Integration Fully Operational!")

if __name__ == "__main__":
    main()
