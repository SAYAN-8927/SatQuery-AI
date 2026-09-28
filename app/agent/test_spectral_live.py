import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.controller import process_user_query

def main():
    print("=" * 65)
    print("TESTING PHASE 7: LIVE SPECTRAL BAND ANALYSIS & PROFILE EXTRACTION")
    print("=" * 65)

    test_query = "Analyze the multispectral bands and extract the spectral reflectance profile for this satellite scene."
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
    print(f"Scene:              {analysis.get('scene')}")
    print(f"Bands Analyzed:     {analysis.get('bands_analyzed')}")
    
    indices = analysis.get("spectral_indices", {})
    print(f"Mean NDVI:          {indices.get('mean_ndvi')}")
    print(f"Mean NDWI (Water):  {indices.get('mean_ndwi')}")
    print(f"Simple Ratio (NIR/R):{indices.get('simple_ratio_nir_red')}")
    print(f"Signature Type:     {analysis.get('spectral_signature_classification')}")

    evidence = analysis.get("evidence", {})
    print(f"Spectral Chart:     {evidence.get('spectral_profile_chart')}")
    print(f"Has VLM Synthesis:  {'vlm_synthesis' in analysis}")

    interpretation = response.get("interpretation", {})
    conf = interpretation.get("confidence", {})
    print(f"Confidence Score:   {conf.get('score')} ({conf.get('level')})")
    print(f"Total Latency:      {total_time}s")
    
    print("\n[Full Interpretation Generated]:")
    print("-" * 65)
    print(interpretation.get("interpretation"))
    print("-" * 65)

    assert response.get("success") is True, "Pipeline execution failed!"
    assert response.get("selected_tool") == "spectral_band_analysis", f"Expected spectral_band_analysis, got {response.get('selected_tool')}"
    assert Path(analysis.get("evidence", {}).get("chart_disk_path", "")).exists(), "Spectral chart file not found on disk!"
    
    print("\n[SUCCESS] Phase 7 Multispectral Band Analysis Fully Verified!")

if __name__ == "__main__":
    main()
