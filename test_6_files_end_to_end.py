import sys
import shutil
from pathlib import Path
import json

from app.services.image_validation import validate_file_extension, validate_tiff
from app.services.image_classification import classify_image
from app.services.band_identifier import identify_landsat_band
from app.services.sar_identifier import parse_sar_filename
from app.agent.input_analyzer import analyze_input
from app.agent.tool_selector import find_compatible_sar_scene
from app.tools.optical_sar_fusion import run_optical_sar_analysis

OPTICAL_DIR = Path(r"D:\SIH PROJECT\SATELLITE IMG\port blair\optical image")
SAR_DIR = Path(r"D:\SIH PROJECT\SATELLITE IMG\port blair\SEN1A_SAR_IW_13APR2026_064061_747B_ESA_ST0C00NTD_DV\S1A_IW_GRDH_1SDV_20260413T120120_20260413T120145_064061_080F88_747B.SAFE\measurement")

OPTICAL_FILES = [
    "LC91340522026109SGI00_B2.TIF",
    "LC91340522026109SGI00_B3.TIF",
    "LC91340522026109SGI00_B4.TIF",
    "LC91340522026109SGI00_B5.TIF"
]

SAR_FILES = [
    "s1a-iw-grd-vv-20260413t120120-20260413t120145-064061-080f88-001.tiff",
    "s1a-iw-grd-vh-20260413t120120-20260413t120145-064061-080f88-002.tiff"
]

def main():
    print("=" * 70)
    print("VERIFICATION: 6 ACTUAL SATELLITE FILES END-TO-END AUDIT")
    print("=" * 70)

    # Setup isolated test directory
    test_dir = Path("uploads/workspaces/test_port_blair_6_files")
    test_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["previews", "multispectral", "fusion"]:
        (test_dir / sub).mkdir(parents=True, exist_ok=True)

    print("\n[Step 1] Inspecting and copying 6 actual measurement files to test directory...")
    all_test_files = []
    for f in OPTICAL_FILES:
        src = OPTICAL_DIR / f
        assert src.exists(), f"Optical file missing: {src}"
        dst = test_dir / f
        if not dst.exists():
            shutil.copyfile(src, dst)
        all_test_files.append(dst)

    for f in SAR_FILES:
        src = SAR_DIR / f
        assert src.exists(), f"SAR file missing: {src}"
        dst = test_dir / f
        if not dst.exists():
            try:
                import os
                os.link(src, dst)
            except Exception:
                shutil.copyfile(src, dst)
        all_test_files.append(dst)

    print(f"  Loaded {len(all_test_files)} measurement files in {test_dir}")

    print("\n[Step 2] Validating TIFFs and CRS / GCPs...")
    for f_path in all_test_files:
        ext_res = validate_file_extension(f_path.name)
        assert ext_res["valid"], f"Extension invalid: {f_path.name}"
        tiff_res = validate_tiff(f_path)
        assert tiff_res["valid"], f"TIFF invalid: {f_path.name}"
        meta = tiff_res["metadata"]
        cls = classify_image(f_path.name, meta)
        print(f"  [OK] {f_path.name[:36]}... | CRS: {meta['crs']} | Modality: {cls.get('modality')} | Band: {cls.get('band')}")

    print("\n[Step 3] Analyzing Input & Scene Grouping...")
    analysis = analyze_input([test_dir])

    # Check optical scene grouping
    scenes = [s for s in analysis["scenes"] if s["scene_id"] in {"LC91340522026109SGI00", "S1A_IW_GRD_20260413_064061"}]
    opt_scene = next((s for s in analysis["scenes"] if s["scene_id"] == "LC91340522026109SGI00"), None)
    sar_scene = next((s for s in analysis["scenes"] if s["scene_id"] == "S1A_IW_GRD_20260413_064061"), None)

    assert opt_scene is not None, "Optical Landsat scene LC91340522026109SGI00 was not formed!"
    print(f"  [OK] Optical Scene: {opt_scene['scene_id']} | Bands: {opt_scene['bands']} | Files: {opt_scene['file_count']}")
    assert opt_scene["bands"] == ["B2", "B3", "B4", "B5"], f"Expected B2-B5, got {opt_scene['bands']}"

    assert sar_scene is not None, "SAR Sentinel-1 scene S1A_IW_GRD_20260413_064061 was not formed!"
    print(f"  [OK] SAR Scene: {sar_scene['scene_id']} | Bands: {sar_scene['bands']} | Files: {sar_scene['file_count']}")
    assert "VV" in sar_scene["bands"] and "VH" in sar_scene["bands"], f"Expected VV and VH, got {sar_scene['bands']}"
    assert sar_scene["available_analyses"]["sar_dual_pol"] is True, "sar_dual_pol must be True!"

    # Verify VV and VH are NOT two unrelated scenes
    all_sar_scenes = [s for s in analysis["scenes"] if "S1A_IW_GRD_20260413" in s["scene_id"]]
    assert len(all_sar_scenes) == 1, f"Expected exactly 1 SAR scene for 20260413, got {len(all_sar_scenes)}: {[s['scene_id'] for s in all_sar_scenes]}"
    print(f"  [OK] Verified: VV and VH are unified into exactly 1 SAR scene (NOT two separate scenes)")

    # Verify previews
    sar_previews = sar_scene.get("band_previews", [])
    print(f"  [OK] SAR Band Previews: {[p['band'] for p in sar_previews]}")
    for p in sar_previews:
        preview_rel = p["preview_url"].replace("/uploads/", "")
        p_path = Path("uploads") / preview_rel
        assert p_path.exists(), f"Preview file missing on disk: {p_path}"
        assert p_path.suffix.lower() == ".png", "Preview must be a PNG visualization, not original TIFF"

    # Verify original scientific TIFFs remain unchanged
    for f in SAR_FILES:
        orig = test_dir / f
        assert orig.exists(), f"Measurement file must exist: {orig}"
        assert orig.stat().st_size > 800_000_000, f"Original 845MB measurement TIFF must not be modified or replaced!"
    print("  [OK] Verified: Original 845MB scientific TIFFs remain untouched and uncompressed")

    print("\n[Step 4] Checking Optical + SAR Pairing Compatibility...")
    comp_sar = find_compatible_sar_scene(opt_scene, analysis)
    assert comp_sar is not None, "Compatible SAR scene not found for Landsat-9 Port Blair!"
    assert comp_sar["scene_id"] == sar_scene["scene_id"], f"Expected {sar_scene['scene_id']}, got {comp_sar['scene_id']}"
    print(f"  [OK] Optical Scene '{opt_scene['scene_id']}' successfully paired with SAR Scene '{comp_sar['scene_id']}'")

    print("\n[Step 5] Executing Multimodal Optical + SAR Fusion Analysis...")
    fusion_res = run_optical_sar_analysis(
        upload_dir=test_dir,
        output_dir=test_dir / "fusion",
        target_scene=opt_scene["scene_id"],
        sar_scene=sar_scene["scene_id"]
    )
    assert fusion_res["success"], f"Fusion failed: {fusion_res.get('error')}"
    print("  [OK] Optical + SAR Fusion Succeeded!")
    print(f"    - Mean Optical NDVI: {fusion_res['optical_metrics']['mean_ndvi']:+.3f}")
    print(f"    - Mean SAR VV: {fusion_res['sar_metrics']['mean_sigma0_vv_db']:.2f} dB")
    print(f"    - Mean SAR VH: {fusion_res['sar_metrics']['mean_sigma0_vh_db']:.2f} dB")
    print(f"    - Radar Vegetation Index (RVI): {fusion_res['sar_metrics']['mean_rvi']:.3f}")
    print(f"    - Cross-Sensor Vegetation Agreement: {fusion_res['fusion_metrics']['cross_sensor_vegetation_agreement_pct']:.1f}%")
    print(f"    - Generated 4-Panel Evidence Composite: {fusion_res['evidence']['fusion_composite']}")

    composite_disk = test_dir / "fusion" / Path(fusion_res['evidence']['fusion_composite']).name
    assert composite_disk.exists(), f"Fusion composite image was not written: {composite_disk}"
    print(f"    - Evidence composite verified on disk: {composite_disk} ({composite_disk.stat().st_size} bytes)")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION REQUIREMENTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    main()
