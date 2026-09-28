import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.controller import process_user_query

queries = [
    ("TEST 1", "Is there vegetation in this image?"),
    ("TEST 2", "Calculate NDVI and explain the vegetation."),
    ("TEST 3", "Compare these two dates and tell me what changed."),
    ("TEST 4", "Analyze the spectral characteristics of this image."),
    ("TEST 5", "Analyze this scene using optical and SAR data.")
]

results = []
print("=" * 65)
print("SATQUERY AI — EXECUTING 5 MANDATORY AUDIT SCENARIOS")
print("=" * 65)

for label, q in queries:
    print(f"\n>>> [{label}]: \"{q}\"")
    t0 = time.time()
    res = process_user_query(q)
    elapsed = round(time.time() - t0, 2)

    intent = res.get("intent")
    tool = res.get("selected_tool")
    success = res.get("success")
    interp = res.get("interpretation", {})
    conf = interp.get("confidence", {}) if interp else {}
    analysis = res.get("analysis", {})
    
    # In VLM standalone query, answer is directly in analysis
    if tool == "remote_sensing_vlm":
        has_vlm = bool(analysis.get("answer"))
    else:
        has_vlm = "vlm_synthesis" in analysis
        
    evidence = analysis.get("evidence", {})
    trace = res.get("execution_trace", {})
    steps = [s["step"] for s in trace.get("steps", [])]

    print(f"  Success:    {success}")
    print(f"  Intent:     {intent}")
    print(f"  Tool:       {tool}")
    print(f"  Has VLM:    {has_vlm}")
    print(f"  Confidence: {conf.get('score')} ({conf.get('level')})")
    print(f"  Evidence:   {evidence}")
    print(f"  Latency:    {elapsed}s")
    print(f"  Steps:      {steps}")
    
    full_text = str(interp.get("interpretation", "")) if interp else ""
    first_lines = "\n  ".join(full_text.strip().split("\n")[:4])
    print(f"  Interpretation Preview:\n  {first_lines}")

    results.append({
        "label": label,
        "query": q,
        "success": success,
        "intent": intent,
        "tool": tool,
        "has_vlm": has_vlm,
        "confidence": conf,
        "evidence": evidence,
        "steps": steps,
        "latency_seconds": elapsed,
        "full_interpretation": full_text
    })

out_path = Path("audit_test_suite_results.json")
out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nAll 5 test outputs saved to {out_path.resolve()}")
