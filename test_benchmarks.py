import requests
import time

queries = [
    ("Vegetation VQA", "Is there vegetation in this image?"),
    ("Bi-Temporal Change", "Compare these two dates and tell me what changed."),
    ("Spectral Profile", "Analyze the spectral characteristics of this image."),
    ("Optical + SAR Fusion", "Analyze this scene using optical and SAR data.")
]

for label, q in queries:
    t0 = time.time()
    try:
        r = requests.post("http://127.0.0.1:8000/api/query", json={"query": q}, timeout=60)
        dur = round(time.time() - t0, 2)
        data = r.json()
        print(f"[{label}] Status: {r.status_code} | Success: {data.get('success')} | Tool: {data.get('selected_tool')} | Duration: {dur}s")
        if not data.get('success'):
            print(f"  Error: {data.get('error')}")
        else:
            evidence = data.get('analysis', {}).get('evidence', {})
            print(f"  Evidence Keys: {list(evidence.keys())}")
    except Exception as e:
        print(f"[{label}] Exception: {e}")
