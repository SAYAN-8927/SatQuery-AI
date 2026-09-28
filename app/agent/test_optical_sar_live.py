import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.controller import process_user_query

def main():
    print("=" * 65)
    print("TESTING PHASE 9: LIVE OPTICAL + SAR FUSION ENGINE")
    print("=" * 65)

    test_query = "Perform joint optical and SAR analysis to evaluate vegetation structure, radar backscatter, and surface water."
    print(f"\n[Query]: \"{test_query}\"")
    print("Running process_user_query through Agent Controller...\n")

    t0 = time.time()
    response = process_user_query(test_query)
    total_time = round(time.time() - t0, 2)

    print("-" * 65)
    print(f"Success:                 {response.get('success')}")
    print(f"Detected Intent:         {response.get('intent')}")
    print(f"Selected Tool:           {response.get('selected_tool')}")
    print(f"Tool Description:        {response.get('tool_description')}")

    analysis = response.get("analysis", {})
    print(f"Optical Scene:           {analysis.get('optical_scene')}")
    print(f"SAR Scene:               {analysis.get('sar_scene')}")

    opt_m = analysis.get("optical_metrics", {})
    print(f"Optical Mean NDVI:       {opt_m.get('mean_ndvi')}")
    print(f"Optical Mean NDWI:       {opt_m.get('mean_ndwi')}")
    print(f"Optical Veg Coverage:    {opt_m.get('vegetation_coverage_pct')}%")

    sar_m = analysis.get("sar_metrics", {})
    print(f"SAR Mean VV Backscatter: {sar_m.get('mean_sigma0_vv_db')} dB")
    print(f"SAR Mean VH Backscatter: {sar_m.get('mean_sigma0_vh_db')} dB")
    print(f"Radar Veg Index (RVI):   {sar_m.get('mean_rvi')}")
    print(f"Cross-Polarization Ratio:{sar_m.get('cross_polarization_ratio_db')} dB")
    print(f"SAR Specular Water:      {sar_m.get('sar_specular_water_coverage_pct')}%")

    fus_m = analysis.get("fusion_metrics", {})
    print(f"Classification:          {fus_m.get('environmental_classification')}")
    print(f"Multi-Sensor Agreement:  {fus_m.get('cross_sensor_vegetation_agreement_pct')}%")
    print(f"All-Weather Water:       {fus_m.get('all_weather_water_coverage_pct')}%")
    print(f"Cross-Sensor Corr (r):   {fus_m.get('optical_sar_correlation')}")

    evidence = analysis.get("evidence", {})
    print(f"Fusion Composite Web:    {evidence.get('fusion_composite')}")
    print(f"Fusion Composite Disk:   {evidence.get('composite_disk_path')}")
    print(f"Has VLM Synthesis:       {'vlm_synthesis' in analysis}")

    interpretation = response.get("interpretation", {})
    conf = interpretation.get("confidence", {})
    print(f"Confidence Score:        {conf.get('score')} ({conf.get('level')})")
    print(f"Confidence Basis:        {conf.get('basis')}")
    print(f"Total Latency:           {total_time}s")

    print("\n[Full Multimodal Interpretation Generated]:")
    print("-" * 65)
    print(interpretation.get("interpretation"))
    print("-" * 65)

    assert response.get("success") is True, "Pipeline execution failed!"
    assert response.get("selected_tool") == "optical_sar_model", f"Expected optical_sar_model, got {response.get('selected_tool')}"
    assert Path(evidence.get("composite_disk_path", "")).exists(), "Fusion composite image not found on disk!"

    print("\n[SUCCESS] Phase 9 Optical + SAR Fusion Engine Fully Verified!")

if __name__ == "__main__":
    main()
