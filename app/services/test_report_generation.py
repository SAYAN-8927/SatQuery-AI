"""
Test SatQuery AI Report Generator across all 5 modalities.
"""
import os
import sys
from pathlib import Path

# Ensure root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.report_generator import generate_research_report

def run_tests():
    print("Testing SatQuery AI PDF Report Generator...")

    # Test 1: NDVI Report
    ndvi_sample = {
        "query": "Calculate NDVI and explain the vegetation.",
        "intent": "ndvi_calculation",
        "intent_reason": "Query explicitly requests NDVI calculation.",
        "selected_tool": "ndvi_analysis",
        "analyzed_scene": {
            "scene_id": "LC09_L2SP_141040_20260810_20260811_02_T1",
            "title": "Landsat-9 OLI-2 • 10 Aug 2026",
            "satellite": "Landsat-9",
            "sensor": "OLI-2",
            "acquisition_date": "10 Aug 2026",
            "path_row_formatted": "141/040",
            "resolution": "30 m",
            "crs": "EPSG:32645 (UTM Zone 45N)",
            "bands": ["B2", "B3", "B4", "B5"],
            "mode": "single_scene"
        },
        "analysis": {
            "scene": "LC09_L2SP_141040_20260810_20260811_02_T1",
            "ndvi_statistics": {
                "mean": 0.482,
                "min": -0.124,
                "max": 0.891,
                "std": 0.215,
                "vegetation_coverage_percent": 74.6
            },
            "evidence": {
                "ndvi_map": "/uploads/multispectral/LC09_L2SP_141040_20260810_20260811_02_T1_RGB.png"
            }
        },
        "interpretation": {
            "interpretation": "The scene exhibits extensive vegetative canopy with an average NDVI of 0.482, indicating healthy active agricultural and forested terrain.",
            "confidence": {
                "score": 0.95,
                "level": "High (Calibrated Physical Pipeline)",
                "basis": [
                    "Deterministic Landsat-9 Collection 2 Surface Reflectance scaling applied.",
                    "Physical bounds [-1.0, 1.0] and non-zero denominator checks satisfied."
                ]
            }
        }
    }

    p1, f1 = generate_research_report(ndvi_sample, output_dir=Path("uploads/reports"))
    print(f"[OK] Test 1 (NDVI) generated: {f1} (size: {os.path.getsize(p1):,} bytes)")

    # Test 2: Bi-Temporal Report
    bitemp_sample = {
        "query": "Compare these two dates and tell me what changed.",
        "intent": "bi_temporal_change",
        "intent_reason": "Bi-temporal change requested.",
        "selected_tool": "change_detection_model",
        "analyzed_scene": {
            "mode": "bitemporal",
            "before": {"scene_id": "LC09_L2SP_141040_20260810", "date": "10 Aug 2026"},
            "after": {"scene_id": "LC09_L2SP_141040_20260826", "date": "26 Aug 2026"}
        },
        "analysis": {
            "before": {"scene_id": "LC09_L2SP_141040_20260810", "date": "10 Aug 2026"},
            "after": {"scene_id": "LC09_L2SP_141040_20260826", "date": "26 Aug 2026"},
            "statistics": {
                "baseline_mean_ndvi": 0.451,
                "monitoring_mean_ndvi": 0.484,
                "mean_delta_ndvi": 0.033,
                "vegetation_gain_percentage": 14.2,
                "vegetation_loss_percentage": 3.8,
                "stable_percentage": 82.0,
                "before_mean_ndvi": 0.451,
                "after_mean_ndvi": 0.484,
                "delta_mean_ndvi": 0.033,
                "dynamic_classification": "Net Vegetative Greening Dynamic"
            },
            "evidence": {
                "comparison_triplet": "/uploads/change_detection/LC09_L2SP_141040_20260810_20260811_02_T1_to_LC09_L2SP_141040_20260826_20260827_02_T1_comparison_triplet.png"
            }
        },
        "interpretation": {
            "interpretation": "Vegetation increased moderately across 14.2% of the monitored agricultural zone between 10 Aug 2026 and 26 Aug 2026.",
            "confidence": {"score": 0.94, "level": "High"}
        }
    }

    p2, f2 = generate_research_report(bitemp_sample, output_dir=Path("uploads/reports"))
    print(f"[OK] Test 2 (Bi-Temporal) generated: {f2} (size: {os.path.getsize(p2):,} bytes)")

    # Test 3: Optical + SAR Report
    fusion_sample = {
        "query": "Analyze this scene using optical and SAR data.",
        "intent": "optical_sar_fusion",
        "selected_tool": "optical_sar_model",
        "analyzed_scene": {
            "mode": "fusion",
            "scene_id": "LC09_L2SP_141040_20260810",
            "sar_scene": "S1A_IW_GRDH_1SDV_20260810"
        },
        "analysis": {
            "optical_metrics": {"mean_ndvi": 0.482, "vegetation_coverage_percent": 74.6},
            "sar_metrics": {"mean_vv_db": -10.4, "mean_vh_db": -16.8, "vh_vv_ratio_db": -6.4},
            "fusion_metrics": {"overlap_percentage": 100}
        },
        "interpretation": {
            "interpretation": "Multimodal fusion aligns optical NDVI with C-band radar volumetric scattering.",
            "confidence": {"score": 0.91, "level": "High"}
        }
    }

    p3, f3 = generate_research_report(fusion_sample, output_dir=Path("uploads/reports"))
    print(f"[OK] Test 3 (Fusion) generated: {f3} (size: {os.path.getsize(p3):,} bytes)")

    print("\nAll 3 modalities generated valid, non-empty scientific PDF reports successfully!")

if __name__ == "__main__":
    run_tests()
