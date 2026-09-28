import os
import sys
from pathlib import Path

def run_presentation_semantic_audit():
    print("=" * 70)
    print("SATQUERY AI — PRESENTATION & SEMANTIC CONSISTENCY AUDIT")
    print("=" * 70)

    # -------------------------------------------------------------
    # TEST A & B: Simulated Render VLM Bypass Status & Confidence Text
    # -------------------------------------------------------------
    print("\n[TEST A & B] Simulated Render VLM Bypass & Confidence Semantics...")
    os.environ["RENDER"] = "true"
    if "ENABLE_LOCAL_VLM" in os.environ:
        del os.environ["ENABLE_LOCAL_VLM"]

    from app.agent.controller import process_user_query
    from app.services.report_generator import SatQueryReportGenerator

    vlm_query_render = process_user_query(
        query="Describe what is visible in this image.",
        scene_id="LC09_L2SP_141040_20260826_20260827_02_T1",
        mode="single_scene"
    )

    assert vlm_query_render.get("success") is True, "VLM query failed under Render"
    
    # Check components
    comps = vlm_query_render.get("components", [])
    assert len(comps) > 0, "No components returned"
    vlm_comp = next((c for c in comps if c.get("tool") == "remote_sensing_vlm"), None)
    assert vlm_comp is not None, "VLM component missing from components list"

    # TEST A: Must NOT be 'executed'
    comp_status = vlm_comp.get("status")
    print(f"  • VLM Component Status under Render: '{comp_status}' (Must NOT be 'executed')")
    assert comp_status != "executed", f"FAILED: Render VLM component status was labeled 'executed'!"
    assert comp_status in {"bypassed", "VLM BYPASSED", "offline"}, f"Unexpected status: {comp_status}"

    # Check trace steps
    trace_steps = vlm_query_render.get("execution_trace", {}).get("steps", [])
    exec_step = next((s for s in trace_steps if s.get("step") == "tool_execution" and s.get("status") in {"completed", "bypassed", "failed"}), None)
    assert exec_step is not None, "tool_execution step missing from trace"
    print(f"  • Tool Execution Trace Status: '{exec_step.get('status')}'")
    assert exec_step.get("status") != "executed", "Trace step should not be 'executed'"
    assert exec_step.get("details", {}).get("status") == "VLM BYPASSED", f"Expected 'VLM BYPASSED', got {exec_step.get('details', {}).get('status')}"
    print("  -> TEST A: PASS (Bypassed VLM is NEVER labeled 'executed')")

    # TEST B: Confidence text must not claim successful model synthesis
    conf = vlm_query_render.get("interpretation", {}).get("confidence", {})
    conf_expl = conf.get("explanation", "")
    print(f"  • Confidence Explanation: '{conf_expl}'")
    assert "successful model synthesis" not in conf_expl, "Confidence explanation claimed successful model synthesis!"
    assert conf_expl == "Estimated from deterministic calculations, generated evidence and spatial consistency.", f"Unexpected explanation: {conf_expl}"
    print("  -> TEST B: PASS (Confidence text does not claim successful model synthesis)")

    # -------------------------------------------------------------
    # TEST C: Render Report identifies VLM as bypassed
    # -------------------------------------------------------------
    print("\n[TEST C] Render Report VLM Bypassed Status...")
    generator_render = SatQueryReportGenerator(vlm_query_render)
    assert generator_render.is_vlm_bypassed is True, "generator_render.is_vlm_bypassed should be True"

    pdf_out = Path("test_output_render_report.pdf")
    generator_render.generate_pdf(pdf_out)
    assert pdf_out.exists() and pdf_out.stat().st_size > 1000, "PDF generation failed"
    pdf_out.unlink() # cleanup
    print("  • Report generated successfully under Render mode.")
    print("  • Verified is_vlm_bypassed == True in report generator.")
    print("  -> TEST C: PASS (Render report identifies VLM as bypassed)")

    # -------------------------------------------------------------
    # TEST D: NDVI mean -0.037 cannot produce 'Healthy Photosynthetic Vegetation Present'
    # -------------------------------------------------------------
    print("\n[TEST D] Scientific Finding Audit for Negative NDVI (Mean: -0.037)...")
    # Simulate an NDVI query response on Port Blair (Mean NDVI = -0.037, non-vegetated water/rock)
    negative_ndvi_payload = {
        "success": True,
        "selected_tool": "ndvi_analysis",
        "query": "Calculate NDVI for this scene.",
        "analysis": {
            "tool": "ndvi_analysis",
            "scene_id": "LC91340522026109SGI00",
            "ndvi_statistics": {
                "mean_ndvi": -0.037,
                "mean": -0.037,
                "max": 0.85,
                "min": -0.80,
                "std": 0.32
            },
            "vegetation_coverage": None
        },
        "interpretation": {
            "interpretation": "Mean NDVI is -0.037.",
            "summary": "Non-vegetated surface.",
            "confidence": {"score": 0.95, "level": "high"}
        }
    }

    report_neg = SatQueryReportGenerator(negative_ndvi_payload)
    findings = report_neg._build_final_finding_section()
    # Convert report flowables to text
    finding_text = "".join(str(f) for f in findings)
    print(f"  • Finding Section Content excerpt:")
    for f in findings:
        if hasattr(f, "_cellvalues"):
            for row in f._cellvalues:
                for cell in row:
                    text_content = getattr(cell, "text", str(cell))
                    print(f"    {text_content}")

    assert "Healthy Photosynthetic Vegetation Present" not in finding_text, (
        "CRITICAL ERROR: Mean NDVI of -0.037 produced 'Healthy Photosynthetic Vegetation Present'!"
    )
    assert "Low / Predominantly Non-Vegetated Signal" in finding_text, (
        "Finding title did not reflect low/non-vegetated signal for negative NDVI!"
    )
    print("  -> TEST D: PASS (NDVI mean -0.037 produces neutral non-vegetated finding)")

    # -------------------------------------------------------------
    # TEST E: Local VLM Behavior Remains Enabled & Unchanged
    # -------------------------------------------------------------
    print("\n[TEST E] Local VLM Functionality & Hardware Acceleration...")
    if "RENDER" in os.environ:
        del os.environ["RENDER"]
    from app.tools.vlm_analysis import is_local_vlm_enabled, run_vlm_analysis

    assert is_local_vlm_enabled() is True, "Local VLM should be enabled when RENDER is absent"
    print(f"  • Local is_local_vlm_enabled(): {is_local_vlm_enabled()}")
    
    # Invoke local VLM query
    local_vlm_res = run_vlm_analysis(
        query="Is there vegetation in this scene? Answer concisely.",
        target_scene_id="LC09_L2SP_141040_20260826_20260827_02_T1"
    )
    assert local_vlm_res.get("success") is True, f"Local VLM failed: {local_vlm_res}"
    assert local_vlm_res.get("deployment_constrained") is not True, "Local VLM should not be constrained"
    assert local_vlm_res.get("vlm_available") is True, "Local VLM should be available"
    device_used = local_vlm_res.get("model_metadata", {}).get("device")
    print(f"  • Local VLM Answer: '{local_vlm_res.get('answer')}' (Device: {device_used})")
    print("  -> TEST E: PASS (Local VLM remains fully functional on local GPU)")

    # -------------------------------------------------------------
    # TEST F: Scientific Calculations Unchanged
    # -------------------------------------------------------------
    print("\n[TEST F] Scientific Calculations Consistency Check...")
    from app.services.multispectral_processor import compute_chunked_ndvi_statistics
    from app.tools.spectral_analysis import compute_chunked_spectral_statistics, get_sensor_band_info

    b4_path = Path("uploads/LC91340522026109SGI00_B4.TIF")
    b5_path = Path("uploads/LC91340522026109SGI00_B5.TIF")
    bands = {
        "B2": Path("uploads/LC91340522026109SGI00_B2.TIF"),
        "B3": Path("uploads/LC91340522026109SGI00_B3.TIF"),
        "B4": b4_path,
        "B5": b5_path,
    }

    ndvi_stats = compute_chunked_ndvi_statistics(b4_path, b5_path, chunk_size=1024)
    assert abs(ndvi_stats["mean"] - (-0.037)) < 0.005, f"NDVI changed! Got {ndvi_stats['mean']}"
    print(f"  • Port Blair Full-Res Chunked Mean NDVI: {ndvi_stats['mean']} (Expected: -0.037)")

    _, band_info = get_sensor_band_info("LC91340522026109SGI00")
    spec_stats = compute_chunked_spectral_statistics(bands, band_info, chunk_size=1024)
    ndwi_val = spec_stats["mean_ndwi"]
    assert abs(ndwi_val - 0.1681) < 0.005, f"NDWI changed! Got {ndwi_val}"
    print(f"  • Port Blair Full-Res Chunked Mean NDWI: {ndwi_val:.4f} (Expected: 0.1681)")
    print("  -> TEST F: PASS (Scientific formulas and values are identical and untouched)")

    print("\n" + "=" * 70)
    print("ALL 6 PRESENTATION & SEMANTIC CONSISTENCY AUDIT CHECKS PASSED (6/6 PASS)")
    print("=" * 70)

if __name__ == "__main__":
    run_presentation_semantic_audit()
