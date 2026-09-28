"""
End-to-End Verification & Consistency Audit for SatQuery AI Bi-Temporal Analysis and Report Generation.

Audits:
1. Change Detection Engine Output (app/tools/change_detection.py)
2. Agent Interpretation & Change-VQA (app/agent/result_interpreter.py & controller.py)
3. PDF Research Report Generator (app/services/report_generator.py)
4. Full text extraction across all sections of the generated PDF using pypdf.
"""
import sys
import os
from pathlib import Path
import json

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.agent.controller import process_user_query
from app.services.report_generator import generate_research_report
from pypdf import PdfReader


def main():
    print("=" * 80)
    print("SATQUERY AI: BI-TEMPORAL NUMERICAL CONSISTENCY AUDIT & TEST")
    print("=" * 80)

    before_scene_id = "LC09_L2SP_141040_20260810_20260811_02_T1"
    after_scene_id = "LC09_L2SP_141040_20260826_20260827_02_T1"
    query = "Compare these two dates and tell me what changed."

    print(f"\n[1] Executing End-to-End Bi-Temporal Analysis:")
    print(f"    - Baseline Scene (T1):   {before_scene_id}")
    print(f"    - Monitoring Scene (T2): {after_scene_id}")
    print(f"    - User Query:            '{query}'")

    result = process_user_query(
        query=query,
        mode="bitemporal",
        before_scene_id=before_scene_id,
        after_scene_id=after_scene_id
    )

    assert result.get("success") is True, f"Analysis failed: {result.get('error')}"
    print("\n[OK] Pipeline completed successfully.")
    print(f"     Tool selected: {result.get('selected_tool')}")

    # -------------------------------------------------------------
    # 2. Extract Authoritative Deterministic Statistics
    # -------------------------------------------------------------
    stats = result["analysis"]["statistics"]
    b_mean = stats["baseline_mean_ndvi"]
    a_mean = stats["monitoring_mean_ndvi"]
    d_mean = stats["mean_delta_ndvi"]
    gain = stats["vegetation_gain_percentage"]
    loss = stats["vegetation_loss_percentage"]
    stable = stats["stable_percentage"]
    dyn = stats["dynamic_classification"]

    print("\n" + "=" * 80)
    print("AUTHORITATIVE DETERMINISTIC SOURCE OF TRUTH (change_detection_model):")
    print("=" * 80)
    print(f"  • Baseline Mean NDVI (T1):     {b_mean:.4f}")
    print(f"  • Monitoring Mean NDVI (T2):   {a_mean:.4f}")
    print(f"  • Mean Delta NDVI (ΔNDVI):     {d_mean:+.4f} (calc diff: {a_mean - b_mean:+.4f})")
    print(f"  • Vegetation Gain:             {gain:.1f}% ({gain:.2f}%)")
    print(f"  • Vegetation Loss:             {loss:.1f}% ({loss:.2f}%)")
    print(f"  • Stable Terrain:              {stable:.1f}% ({stable:.2f}%)")
    print(f"  • Dynamic Classification:      {dyn}")

    # Check percentages sum to 100%
    pct_sum = round(gain + loss + stable, 2)
    print(f"  • Total Percentage Sum:        {pct_sum}%")
    assert abs(pct_sum - 100.0) <= 0.05, f"Percentage sum error: {pct_sum}% != 100%"
    print("  ✓ PASS: Gain % + Loss % + Stable % = 100.00%")

    # -------------------------------------------------------------
    # 3. Check AI Qualitative Synthesis text
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("CHECKING AI QUALITATIVE INTERPRETATION:")
    print("=" * 80)
    interp_text = result["interpretation"]["interpretation"]
    print(interp_text)

    b_str_4 = f"{b_mean:.4f}"
    a_str_4 = f"{a_mean:.4f}"
    d_str_4 = f"{d_mean:+.4f}"
    gain_str_1 = f"{gain:.1f}%"
    loss_str_1 = f"{loss:.1f}%"
    stable_str_1 = f"{stable:.1f}%"

    assert b_str_4 in interp_text, f"Baseline {b_str_4} missing from AI text!"
    assert a_str_4 in interp_text, f"Monitoring {a_str_4} missing from AI text!"
    assert d_str_4 in interp_text, f"Delta {d_str_4} missing from AI text!"
    assert gain_str_1 in interp_text, f"Gain {gain_str_1} missing from AI text!"
    assert loss_str_1 in interp_text, f"Loss {loss_str_1} missing from AI text!"
    assert stable_str_1 in interp_text, f"Stable {stable_str_1} missing from AI text!"
    print("  ✓ PASS: AI Qualitative Synthesis contains exact authoritative numbers.")

    # -------------------------------------------------------------
    # 4. Generate Research PDF Report
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("GENERATING PDF RESEARCH REPORT:")
    print("=" * 80)
    reports_dir = Path("uploads/reports")
    pdf_path, filename = generate_research_report(result, output_dir=reports_dir)
    print(f"  PDF Generated: {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")

    # -------------------------------------------------------------
    # 5. Extract & Audit PDF Text across All Sections
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("AUDITING GENERATED PDF TEXT WITH PYPDF:")
    print("=" * 80)
    reader = PdfReader(str(pdf_path))
    num_pages = len(reader.pages)
    print(f"  Total Pages in PDF: {num_pages}")

    full_pdf_text = ""
    for idx, page in enumerate(reader.pages, 1):
        txt = page.extract_text() or ""
        full_pdf_text += f"\n--- PAGE {idx} ---\n" + txt

    # Check Section 3 wording
    print("\n[Audit Item A] Scientific Methods Wording:")
    assert "clipped to physical reflectance limits [-1,+1]" not in full_pdf_text, (
        "ERROR: Found obsolete 'clipped to physical reflectance limits' wording in PDF!"
    )
    assert "Surface Reflectance Calibration" in full_pdf_text, "ERROR: Missing Surface Reflectance Calibration in PDF!"
    assert "unit physical surface reflectance [0.0, 1.0]" in full_pdf_text or "[0.0, 1.0]" in full_pdf_text, (
        "ERROR: Missing [0.0, 1.0] reflectance calibration in PDF!"
    )
    assert "[-1.0, +1.0]" in full_pdf_text, "ERROR: Missing [-1.0, +1.0] mathematical range in PDF!"
    print("  ✓ PASS: Wording correctly distinguishes surface reflectance [0.0, 1.0] from mathematical range [-1.0, +1.0].")

    # Check Section 4: Quantitative Scientific Results
    print("\n[Audit Item B] Quantitative Scientific Results Section:")
    assert "4. Quantitative Scientific Results" in full_pdf_text
    assert "Baseline Mean NDVI (T1)" in full_pdf_text
    assert "Monitoring Mean NDVI (T2)" in full_pdf_text
    assert "Net Difference" in full_pdf_text and ("\u0394NDVI" in full_pdf_text or "\u2206NDVI" in full_pdf_text)
    assert "Vegetation Gain Ratio" in full_pdf_text
    assert "Vegetation Loss Ratio" in full_pdf_text
    assert "Stable Surface Ratio" in full_pdf_text

    # Verify NO "Not available" appears in Section 4 table
    # We can isolate section 4
    sec4_text = full_pdf_text.split("4. Quantitative Scientific Results")[1].split("5. Visual Evidence Artifacts")[0]
    print("  Extract of Section 4 Table:")
    for line in sec4_text.strip().split("\n"):
        if any(k in line for k in ["Baseline", "Monitoring", "Net Difference", "Vegetation Gain", "Vegetation Loss", "Stable Surface", "Dynamic"]):
            print("    ", line.strip())
        elif any(v in line for v in [b_str_4, a_str_4, d_str_4, gain_str_1, loss_str_1, stable_str_1]):
            print("    ", line.strip())

    assert "Not available" not in sec4_text, f"ERROR: 'Not available' found in Section 4:\n{sec4_text}"
    assert b_str_4 in sec4_text, f"ERROR: Baseline {b_str_4} not found in Section 4!"
    assert a_str_4 in sec4_text, f"ERROR: Monitoring {a_str_4} not found in Section 4!"
    assert d_str_4 in sec4_text, f"ERROR: Net Difference {d_str_4} not found in Section 4!"
    assert gain_str_1 in sec4_text, f"ERROR: Gain {gain_str_1} not found in Section 4!"
    assert loss_str_1 in sec4_text, f"ERROR: Loss {loss_str_1} not found in Section 4!"
    assert stable_str_1 in sec4_text, f"ERROR: Stable {stable_str_1} not found in Section 4!"
    print("  ✓ PASS: Section 4 displays all exact authoritative numbers with ZERO 'Not available'.")

    # Check Section 6: AI Qualitative Synthesis
    print("\n[Audit Item C] AI Qualitative Synthesis Section:")
    sec6_text = full_pdf_text.split("6. AI Vision-Language Qualitative Synthesis")[1].split("7. Final Finding")[0]
    assert b_str_4 in sec6_text, f"ERROR: Baseline {b_str_4} not found in Section 6!"
    assert a_str_4 in sec6_text, f"ERROR: Monitoring {a_str_4} not found in Section 6!"
    assert d_str_4 in sec6_text, f"ERROR: Delta {d_str_4} not found in Section 6!"
    assert gain_str_1 in sec6_text, f"ERROR: Gain {gain_str_1} not found in Section 6!"
    assert loss_str_1 in sec6_text, f"ERROR: Loss {loss_str_1} not found in Section 6!"
    assert stable_str_1 in sec6_text, f"ERROR: Stable {stable_str_1} not found in Section 6!"
    print("  ✓ PASS: Section 6 contains identical authoritative values.")

    # Check Section 7: Final Finding & Synthesis
    print("\n[Audit Item D] Final Finding & Synthesis Section:")
    sec7_text = full_pdf_text.split("7. Final Finding & Synthesis")[1].split("8. Estimated Evidence")[0]
    print("  Extract of Section 7:")
    print("    ", sec7_text.strip().replace("\n", " "))
    assert b_str_4 in sec7_text, f"ERROR: Baseline {b_str_4} not found in Section 7!"
    assert a_str_4 in sec7_text, f"ERROR: Monitoring {a_str_4} not found in Section 7!"
    assert d_str_4 in sec7_text, f"ERROR: Delta {d_str_4} not found in Section 7!"
    assert gain_str_1 in sec7_text, f"ERROR: Gain {gain_str_1} not found in Section 7!"
    assert loss_str_1 in sec7_text, f"ERROR: Loss {loss_str_1} not found in Section 7!"
    assert stable_str_1 in sec7_text, f"ERROR: Stable {stable_str_1} not found in Section 7!"
    assert "ΔNDVI +0.000" not in sec7_text and "∆NDVI +0.000" not in sec7_text, "ERROR: Found obsolete +0.000 fallback in Section 7!"
    assert "0.0% loss" not in sec7_text and "0.0% remaining" not in sec7_text, "ERROR: Found 0.0% fallbacks in Section 7!"
    print("  ✓ PASS: Section 7 contains identical authoritative values.")

    # -------------------------------------------------------------
    # SUMMARY CONSISTENCY TABLE
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("NUMERICAL CONSISTENCY VERIFICATION SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Metric':<28} | {'Engine Truth':<14} | {'Quantitative':<14} | {'AI Synthesis':<14} | {'Final Finding':<14}")
    print("-" * 92)
    print(f"{'Baseline Mean NDVI (T1)':<28} | {b_str_4:<14} | {b_str_4:<14} | {b_str_4:<14} | {b_str_4:<14}")
    print(f"{'Monitoring Mean NDVI (T2)':<28} | {a_str_4:<14} | {a_str_4:<14} | {a_str_4:<14} | {a_str_4:<14}")
    print(f"{'Net Delta (ΔNDVI)':<28} | {d_str_4:<14} | {d_str_4:<14} | {d_str_4:<14} | {d_str_4:<14}")
    print(f"{'Vegetation Gain':<28} | {gain_str_1:<14} | {gain_str_1:<14} | {gain_str_1:<14} | {gain_str_1:<14}")
    print(f"{'Vegetation Loss':<28} | {loss_str_1:<14} | {loss_str_1:<14} | {loss_str_1:<14} | {loss_str_1:<14}")
    print(f"{'Stable Terrain':<28} | {stable_str_1:<14} | {stable_str_1:<14} | {stable_str_1:<14} | {stable_str_1:<14}")
    print("-" * 92)
    print(f"Percentage Total: {gain:.2f}% + {loss:.2f}% + {stable:.2f}% = {pct_sum:.2f}%")
    print("\nALL SECTIONS VERIFIED 100% IDENTICAL AND CONSISTENT!")
    print(f"Generated PDF File: {pdf_path.resolve()}")
    print("=" * 80)


if __name__ == "__main__":
    main()
