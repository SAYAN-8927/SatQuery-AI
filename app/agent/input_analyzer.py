from pathlib import Path
import re


from datetime import datetime

LANDSAT_PATTERN = re.compile(
    r"^(?P<scene>(?:LC\d{2}_[A-Z0-9]{4}_\d{6}_\d{8}_\d{8}_\d{2}_[A-Z0-9]{2}|L[CEMT][4-9]\d{13}[A-Z0-9]{5}|LC0?[89]_[A-Z0-9_]+?|LC[89][A-Z0-9_]+?))"
    r"(?:_SR)?_(?P<band>B(?:[1-9]|1[0-1]))\.TIFF?$",
    re.IGNORECASE
)

from app.services.sar_identifier import parse_sar_filename, BENCH_SAR_PATTERN as SAR_PATTERN


def analyze_input(upload_dir: Path | list[Path]):
    """
    Analyze uploaded remote-sensing files and group
    Landsat optical, Sentinel-1 SAR bands, and generic single-image
    remote sensing / aerial uploads into scenes.
    """

    if isinstance(upload_dir, (list, tuple)):
        dirs = [Path(d) for d in upload_dir if Path(d).exists()]
    else:
        dirs = [Path(upload_dir)] if Path(upload_dir).exists() else []

    primary_upload_dir = dirs[0] if dirs else Path("uploads")

    files = []
    seen_names = set()

    for target_dir in dirs:
        for file_path in target_dir.iterdir():

            if not file_path.is_file():
                continue

            # Skip auxiliary metadata and generated artifact files in root
            fname_lower = file_path.name.lower()
            if fname_lower.endswith(".aux.xml"):
                continue
            if any(fname_lower.endswith(sfx) for sfx in ["_preview.png", "_ndvi.png", "_diff.png", "_change.png"]):
                continue

            # De-duplicate files if present in multiple search paths
            if file_path.name in seen_names:
                continue
            seen_names.add(file_path.name)

            landsat_match = LANDSAT_PATTERN.match(file_path.name)
            sar_info = parse_sar_filename(file_path.name)

            if landsat_match:
                scene_id = landsat_match.group("scene")
                band = landsat_match.group("band").upper()

                files.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "scene_id": scene_id,
                    "band": band,
                    "modality": "optical"
                })

            elif sar_info:
                scene_id = sar_info["scene_id"]
                band = sar_info["polarization"]

                files.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "scene_id": scene_id,
                    "band": band,
                    "modality": "sar",
                    "satellite": sar_info.get("satellite", "Sentinel-1A"),
                    "sensor": sar_info.get("sensor", "C-SAR (Synthetic Aperture Radar)"),
                    "date_str": sar_info.get("date_str"),
                    "date_formatted": sar_info.get("date"),
                    "date_int": sar_info.get("date_int", 0)
                })

            elif file_path.suffix.lower() in {".tif", ".tiff"}:
                # Check whether this TIFF is a single-band scientific raster dataset
                is_single_band_geo = False
                geo_crs = None
                geo_res = None
                try:
                    import rasterio
                    with rasterio.open(file_path) as ds:
                        if ds.count == 1:
                            is_single_band_geo = True
                            if ds.crs and str(ds.crs) != "None":
                                geo_crs = str(ds.crs)
                            if ds.res and len(ds.res) >= 2:
                                rx = ds.res[0]
                                geo_res = f"{int(rx)} m" if rx == int(rx) else f"{rx:.1f} m"
                except Exception:
                    pass

                clean_stem = re.sub(r"[^\w\-_]", "_", file_path.stem).strip("_")
                scene_id = clean_stem or f"IMG_{file_path.stem}"

                if is_single_band_geo:
                    files.append({
                        "filename": file_path.name,
                        "path": str(file_path.resolve()),
                        "scene_id": scene_id,
                        "band": "Band 1",
                        "modality": "optical",
                        "is_generic_image": False,
                        "is_single_band_raster": True,
                        "crs": geo_crs or "Not available",
                        "resolution": geo_res or "Not available",
                        "width": None,
                        "height": None,
                        "channels": "1",
                        "image_format": "TIFF",
                        "input_category": "single_band_raster"
                    })
                else:
                    # Multi-band visual TIFF without Landsat naming, treated as visual image
                    files.append({
                        "filename": file_path.name,
                        "path": str(file_path.resolve()),
                        "scene_id": scene_id,
                        "band": "RGB",
                        "modality": "optical",
                        "is_generic_image": True,
                        "channels": "RGB",
                        "image_format": "TIFF",
                        "input_category": "single_image_vqa"
                    })

            elif file_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                # Generic single-image remote sensing / aerial photo / screenshot upload
                clean_stem = re.sub(r"[^\w\-_]", "_", file_path.stem).strip("_")
                scene_id = clean_stem or f"IMG_{file_path.stem}"

                # Extract real image dimensions & channels
                img_width = None
                img_height = None
                img_channels = "RGB"
                img_format = file_path.suffix.upper().lstrip(".")
                try:
                    from PIL import Image
                    with Image.open(file_path) as im:
                        img_width, img_height = im.size
                        img_channels = im.mode
                        if im.format:
                            img_format = im.format
                except Exception:
                    pass

                files.append({
                    "filename": file_path.name,
                    "path": str(file_path.resolve()),
                    "scene_id": scene_id,
                    "band": "RGB",
                    "modality": "optical",
                    "is_generic_image": True,
                    "width": img_width,
                    "height": img_height,
                    "channels": img_channels,
                    "image_format": img_format,
                    "input_category": "single_image_vqa"
                })

            else:
                files.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "scene_id": None,
                    "band": None,
                    "modality": "unknown"
                })

    # --------------------------------------------------
    # Group files by scene
    # --------------------------------------------------

    scene_groups = {}

    for file in files:

        scene_id = file.get("scene_id")

        if scene_id is None:
            continue

        if scene_id not in scene_groups:
            scene_groups[scene_id] = []

        scene_groups[scene_id].append(file)

    # --------------------------------------------------
    # Build scene information
    # --------------------------------------------------

    scenes = []

    for scene_id, scene_files in scene_groups.items():

        is_generic = any(f.get("is_generic_image") for f in scene_files)

        if is_generic:
            f0 = scene_files[0]
            f_path = Path(f0["path"])
            scene_modality = "optical"
            bands = ["RGB"]
            available_analyses = {
                "vlm_visual_qa": True,
                "rgb": True,
                "ndvi": False,
                "multispectral": False,
                "sar_backscatter": False
            }

            img_width = f0.get("width")
            img_height = f0.get("height")
            img_channels = f0.get("channels", "RGB")
            img_format = f0.get("image_format", f_path.suffix.upper().lstrip("."))

            if not img_width or not img_height:
                try:
                    from PIL import Image
                    with Image.open(f_path) as im:
                        img_width, img_height = im.size
                        img_channels = im.mode
                        if im.format:
                            img_format = im.format
                except Exception:
                    pass

            dimensions_str = f"{img_width} × {img_height}" if img_width and img_height else "Standard Resolution"

            # Date extraction from filename (e.g. 2026-09-20 or 20260920) or file mtime
            date_formatted = None
            date_int = 0
            upload_timestamp = None
            date_match = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", f_path.name)
            if date_match:
                y, m, d = date_match.group(1), date_match.group(2), date_match.group(3)
                try:
                    dt = datetime(int(y), int(m), int(d))
                    date_formatted = dt.strftime("%d %b %Y")
                    date_int = int(f"{y}{m}{d}")
                except Exception:
                    pass

            try:
                mtime = f_path.stat().st_mtime
                dt = datetime.fromtimestamp(mtime)
                upload_timestamp = dt.strftime("%d %b %Y, %H:%M:%S")
                if not date_formatted:
                    date_formatted = dt.strftime("%d %b %Y")
                    date_int = int(dt.strftime("%Y%m%d"))
            except Exception:
                if not date_formatted:
                    date_formatted = "Active Scene"
                upload_timestamp = "Recent Upload"

            fname_lower = f_path.name.lower()
            if "screenshot" in fname_lower:
                satellite = "Captured Aerial Image"
                sensor = "RGB Visual Screen Capture"
            elif any(k in fname_lower for k in ["uav", "drone"]):
                satellite = "UAV / Drone Platform"
                sensor = "Aerial RGB Sensor"
            else:
                satellite = "Single RGB Image"
                sensor = "Standard RGB Camera / Visual Sensor"

            # Requirement #6: Truthful metadata for standard PNG/JPEG
            # Do NOT invent CRS, satellite name, bands, coordinates, etc.
            crs = "Not available"
            geospatial_metadata = "Not available"
            resolution = "Not available (Non-georeferenced)"
            path_row = None
            path_row_formatted = None

            # Resolve preview URL relative to uploads directory
            try:
                rel_path = f_path.resolve().relative_to(Path("uploads").resolve()).as_posix()
                preview_url = f"/uploads/{rel_path}"
            except Exception:
                preview_url = f"/uploads/{f_path.name}"

            # Create preview if it's a TIFF
            if f_path.suffix.lower() in {".tif", ".tiff"}:
                preview_dir = f_path.parent / "previews"
                preview_dir.mkdir(parents=True, exist_ok=True)
                p_file = preview_dir / f"{f_path.stem}_preview.png"
                if not p_file.exists():
                    try:
                        from app.services.raster_preprocessor import create_preview
                        create_preview(f_path, preview_dir, size=512)
                    except Exception:
                        pass
                if p_file.exists():
                    try:
                        rel = p_file.resolve().relative_to(Path("uploads").resolve()).as_posix()
                        preview_url = f"/uploads/{rel}"
                    except Exception:
                        preview_url = f"/uploads/previews/{p_file.name}"

            thumbnail_url = preview_url
            band_previews = [{
                "band": "RGB",
                "name": "True-Color Visual",
                "wavelength": "Visual 400-700 nm",
                "preview_url": preview_url,
                "color": "#38bdf8"
            }]
            composite_previews = [{
                "type": "RGB",
                "label": "True-Color Visual",
                "url": preview_url
            }]

            display_title = f"{satellite} • {f_path.name}"

            scenes.append({
                "scene_id": scene_id,
                "title": display_title,
                "name": f"{satellite} ({img_format})",
                "satellite": satellite,
                "sensor": sensor,
                "path_row": path_row,
                "path_row_formatted": path_row_formatted,
                "date_int": date_int,
                "date": date_formatted,
                "acquisition_date": date_formatted,
                "upload_timestamp": upload_timestamp,
                "crs": crs,
                "geospatial_metadata": geospatial_metadata,
                "resolution": resolution,
                "file_count": 1,
                "bands": bands,
                "modality": scene_modality,
                "available_analyses": available_analyses,
                "thumbnail": thumbnail_url,
                "thumbnail_url": thumbnail_url,
                "band_previews": band_previews,
                "composite_previews": composite_previews,
                "can_delete": True,
                "is_generic_image": True,
                "input_category": "single_image_vqa",
                "source_file": f_path.name,
                "image_path": str(f_path.resolve()),
                "image_format": img_format,
                "width": img_width,
                "height": img_height,
                "dimensions": dimensions_str,
                "channels": img_channels
            })
            continue

        bands = sorted(
            file["band"]
            for file in scene_files
            if file.get("band")
        )

        is_sar = any(f.get("modality") == "sar" for f in scene_files)
        scene_modality = "sar" if is_sar else "optical"

        if is_sar:
            available_analyses = {
                "sar_dual_pol": "VV" in bands and "VH" in bands,
                "sar_backscatter": "VV" in bands or "VH" in bands
            }
        else:
            available_analyses = {
                "ndvi": "B4" in bands and "B5" in bands,
                "rgb": all(
                    band in bands
                    for band in ["B2", "B3", "B4"]
                ),
                "multispectral": all(
                    band in bands
                    for band in ["B2", "B3", "B4", "B5"]
                )
            }

        # Metadata resolution
        date_str = None
        date_formatted = None
        date_int = 0
        satellite = "Remote Sensing Satellite"
        sensor = "Multispectral Sensor"
        crs = "EPSG:32645"
        resolution = "30 m"
        path_row = None
        path_row_formatted = None

        # Standard Landsat scene naming format: L[CEMT][4-9][PPP][RRR][YYYY][DDD][GGG][VV]
        m_std = re.match(r"^L[CEMT]([4-9])(\d{3})(\d{3})(\d{4})(\d{3})[A-Z0-9]{5}$", scene_id)
        is_single_band_raster = any(f.get("is_single_band_raster") for f in scene_files)

        if is_sar:
            first_sar = scene_files[0]
            satellite = first_sar.get("satellite", "Sentinel-1A")
            sensor = first_sar.get("sensor", "C-SAR (Synthetic Aperture Radar)")
            crs = "EPSG:4326 (WGS84)"
            resolution = "10 m"
            if first_sar.get("date_formatted"):
                date_formatted = first_sar.get("date_formatted")
            if first_sar.get("date_int"):
                date_int = first_sar.get("date_int")
            if first_sar.get("date_str"):
                date_str = first_sar.get("date_str")
            if not date_str:
                for part in scene_id.split("_"):
                    if len(part) >= 8 and part[:8].isdigit():
                        date_str = part[:8]
                        break
        elif m_std:
            sat_num = m_std.group(1)
            satellite = f"Landsat-{sat_num}"
            sensor = "OLI-2 (Operational Land Imager 2)" if sat_num == "9" else ("OLI (Operational Land Imager)" if sat_num == "8" else "ETM+ / TM")
            p_str = m_std.group(2)
            r_str = m_std.group(3)
            path_row = f"{p_str}{r_str}"
            path_row_formatted = f"{p_str}/{r_str}"
            year = int(m_std.group(4))
            julian_day = int(m_std.group(5))
            try:
                from datetime import date as dt_date, timedelta
                d = dt_date(year, 1, 1) + timedelta(days=julian_day - 1)
                date_str = d.strftime("%Y%m%d")
                date_formatted = d.strftime("%d %b %Y")
                date_int = int(d.strftime("%Y%m%d"))
            except Exception:
                pass
        elif scene_id.startswith("LC09") or scene_id.startswith("LC9"):
            satellite = "Landsat-9"
            sensor = "OLI-2 (Operational Land Imager 2)"
            parts = scene_id.split("_")
            if len(parts) > 2 and len(parts[2]) == 6 and parts[2].isdigit():
                path_row = parts[2]
                path_row_formatted = f"{parts[2][:3]}/{parts[2][3:]}"
            if len(parts) > 3 and parts[3].isdigit():
                date_str = parts[3]
        elif scene_id.startswith("LC08") or scene_id.startswith("LC8"):
            satellite = "Landsat-8"
            sensor = "OLI (Operational Land Imager)"
            parts = scene_id.split("_")
            if len(parts) > 2 and len(parts[2]) == 6 and parts[2].isdigit():
                path_row = parts[2]
                path_row_formatted = f"{parts[2][:3]}/{parts[2][3:]}"
            if len(parts) > 3 and parts[3].isdigit():
                date_str = parts[3]
        elif is_single_band_raster:
            satellite = "Earth Observation Platform"
            sensor = "Single-Band Calibrated Sensor"

        # Authoritatively inspect physical GeoTIFF raster header for real CRS and resolution
        if scene_files:
            try:
                import rasterio
                with rasterio.open(scene_files[0]["path"]) as ds:
                    if ds.crs and str(ds.crs) != "None":
                        crs = str(ds.crs)
                    elif ds.gcps and ds.gcps[1]:
                        crs = f"{ds.gcps[1]} (WGS84)"
                    if ds.res and len(ds.res) >= 2 and ds.crs:
                        rx = ds.res[0]
                        if rx > 0 and rx != 1.0:
                            resolution = f"{int(rx)} m" if rx == int(rx) else f"{rx:.1f} m"
            except Exception:
                pass

        if date_str and len(date_str) == 8 and date_str.isdigit():
            date_int = int(date_str)
            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
                date_formatted = dt.strftime("%d %b %Y")
            except Exception:
                date_formatted = date_str

        # --------------------------------------------------
        # Visual Previews & Thumbnail Resolution
        # --------------------------------------------------
        first_file_dir = Path(scene_files[0]["path"]).parent
        preview_dir = first_file_dir / "previews"
        if not preview_dir.exists() and (primary_upload_dir / "previews").exists():
            preview_dir = primary_upload_dir / "previews"
        preview_dir.mkdir(parents=True, exist_ok=True)

        multispectral_dir = first_file_dir / "multispectral"
        if not multispectral_dir.exists() and (primary_upload_dir / "multispectral").exists():
            multispectral_dir = primary_upload_dir / "multispectral"

        band_previews = []
        thumbnail_url = None
        composite_previews = []

        if is_sar:
            for f in scene_files:
                b = f.get("band")
                p_file = preview_dir / f"{Path(f['path']).stem}_preview.png"
                if not p_file.exists():
                    try:
                        from app.services.raster_preprocessor import create_preview
                        create_preview(Path(f["path"]), preview_dir, size=512)
                    except Exception:
                        pass
                if p_file.exists():
                    try:
                        rel_path = p_file.relative_to(Path("uploads")).as_posix()
                        rel_url = f"/uploads/{rel_path}"
                    except Exception:
                        rel_url = f"/uploads/previews/{p_file.name}"
                    band_previews.append({
                        "band": b,
                        "name": f"{'VV Backscatter' if b == 'VV' else 'VH Cross-Pol'} (dB)",
                        "wavelength": "C-Band 5.405 GHz",
                        "preview_url": rel_url,
                        "color": "#a855f7" if b == "VV" else "#ec4899"
                    })
                    if not thumbnail_url or b == "VV":
                        thumbnail_url = rel_url
            composite_previews.append({
                "type": "SAR",
                "label": "C-SAR Radar Dual-Pol",
                "url": thumbnail_url or "/uploads/previews/S1A_IW_GRDH_1SDV_20260810_VV_preview.png"
            })
        else:
            # Optical Bands B2, B3, B4, B5
            band_info_map = {
                "B2": ("Blue", "0.48 µm", "#38bdf8"),
                "B3": ("Green", "0.56 µm", "#10b981"),
                "B4": ("Red", "0.65 µm", "#ef4444"),
                "B5": ("NIR", "0.86 µm", "#8b5cf6")
            }
            for f in scene_files:
                b = f.get("band")
                p_file = preview_dir / f"{Path(f['path']).stem}_preview.png"
                if not p_file.exists():
                    try:
                        from app.services.raster_preprocessor import create_preview
                        create_preview(Path(f["path"]), preview_dir, size=512)
                    except Exception:
                        pass
                if p_file.exists():
                    label, wave, color = band_info_map.get(b, (b, "", "#00e5ff"))
                    try:
                        rel_path = p_file.relative_to(Path("uploads")).as_posix()
                        rel_url = f"/uploads/{rel_path}"
                    except Exception:
                        rel_url = f"/uploads/previews/{p_file.name}"
                    band_previews.append({
                        "band": b,
                        "name": label,
                        "wavelength": wave,
                        "preview_url": rel_url,
                        "color": color
                    })

            # Check RGB composite
            rgb_file = multispectral_dir / f"{scene_id}_RGB.png"
            if not rgb_file.exists():
                cd_rgb = first_file_dir / "change_detection" / f"{scene_id}_RGB.png"
                if not cd_rgb.exists() and (primary_upload_dir / "change_detection").exists():
                    cd_rgb = primary_upload_dir / "change_detection" / f"{scene_id}_RGB.png"
                if cd_rgb.exists():
                    rgb_file = cd_rgb

            if rgb_file.exists():
                try:
                    rel_path = rgb_file.relative_to(Path("uploads")).as_posix()
                    thumbnail_url = f"/uploads/{rel_path}"
                except Exception:
                    thumbnail_url = f"/uploads/{rgb_file.parent.name}/{rgb_file.name}"
                composite_previews.append({
                    "type": "RGB",
                    "label": "True-Color RGB (B4, B3, B2)",
                    "url": thumbnail_url
                })
            elif band_previews:
                b4_p = next((bp for bp in band_previews if bp["band"] == "B4"), None)
                thumbnail_url = b4_p["preview_url"] if b4_p else band_previews[0]["preview_url"]

            # Check NIR preview
            nir_file = multispectral_dir / f"{scene_id}_NIR.png"
            if nir_file.exists():
                try:
                    rel_path = nir_file.relative_to(Path("uploads")).as_posix()
                    nir_url = f"/uploads/{rel_path}"
                except Exception:
                    nir_url = f"/uploads/multispectral/{nir_file.name}"
                composite_previews.append({
                    "type": "NIR",
                    "label": "Near-Infrared Composite (B5)",
                    "url": nir_url
                })
            else:
                b5_p = next((bp for bp in band_previews if bp["band"] == "B5"), None)
                if b5_p:
                    composite_previews.append({
                        "type": "NIR",
                        "label": "Near-Infrared (B5)",
                        "url": b5_p["preview_url"]
                    })

        display_title = f"{satellite} {sensor.split()[0]} • {date_formatted or 'Active Scene'}"

        scenes.append({
            "scene_id": scene_id,
            "title": display_title,
            "name": f"{satellite} {sensor.split()[0]}",
            "satellite": satellite,
            "sensor": sensor,
            "path_row": path_row,
            "path_row_formatted": path_row_formatted,
            "date_int": date_int,
            "date": date_formatted or "Active Scene",
            "acquisition_date": date_formatted or "Active Scene",
            "crs": crs,
            "resolution": resolution,
            "file_count": len(scene_files),
            "bands": bands,
            "modality": scene_modality,
            "available_analyses": available_analyses,
            "thumbnail": thumbnail_url,
            "thumbnail_url": thumbnail_url,
            "band_previews": band_previews,
            "composite_previews": composite_previews,
            "can_delete": True
        })

    # --------------------------------------------------
    # Detect bi-temporal pair (Optical scenes with NDVI)
    # Strict Remote-Sensing Compatibility Rules:
    # 1. SAME Path/Row - mandatory for Landsat pixel-wise pairing
    # 2. SAME spatial extent / compatible CRS grid
    # 3. Both scenes must contain required optical bands B4 + B5
    # 4. Prefer SAME satellite/sensor when available
    # 5. Different acquisition dates (chronologically ordered before < after)
    # 6. If multiple valid pairs, rank by same satellite, minimal positive interval
    # 7. SAR scenes must NEVER be selected as optical change-detection scenes
    # --------------------------------------------------

    bi_temporal_pairs = []

    # Filter: strictly optical scenes with B4 and B5 (NDVI capable) and valid path_row
    # (SAR scenes are automatically excluded because modality != 'optical')
    optical_ndvi_scenes = [
        s for s in scenes
        if s.get("modality") == "optical"
        and s.get("available_analyses", {}).get("ndvi")
        and s.get("path_row") is not None
        and s.get("date_int", 0) > 0
    ]

    valid_pairs = []

    for i in range(len(optical_ndvi_scenes)):
        for j in range(i + 1, len(optical_ndvi_scenes)):
            s1 = optical_ndvi_scenes[i]
            s2 = optical_ndvi_scenes[j]

            # Priority 1: MANDATORY identical Path/Row
            if s1.get("path_row") != s2.get("path_row"):
                continue

            # Priority 2: Compatible CRS
            if s1.get("crs") != s2.get("crs"):
                continue

            # Priority 5: Different acquisition dates
            d1_int = s1.get("date_int", 0)
            d2_int = s2.get("date_int", 0)
            if d1_int == d2_int:
                continue

            # Chronological ordering: before = earlier, after = later
            if d1_int < d2_int:
                before, after = s1, s2
                before_int, after_int = d1_int, d2_int
            else:
                before, after = s2, s1
                before_int, after_int = d2_int, d1_int

            # Calculate interval days
            interval_days = 0
            try:
                d_before = datetime.strptime(str(before_int), "%Y%m%d")
                d_after = datetime.strptime(str(after_int), "%Y%m%d")
                interval_days = (d_after - d_before).days
            except Exception:
                interval_days = 0

            # Priority 4: Same satellite preference
            same_sat = (before.get("satellite") == after.get("satellite"))

            valid_pairs.append({
                "before": before,
                "after": after,
                "before_date": before.get("acquisition_date", "Before Scene"),
                "after_date": after.get("acquisition_date", "After Scene"),
                "interval_days": interval_days,
                "path_row": before.get("path_row"),
                "path_row_formatted": before.get("path_row_formatted"),
                "crs": before.get("crs"),
                "same_satellite": same_sat,
                "detection_method": f"Automatic Temporal NDVI Coregistration (Path/Row {before.get('path_row_formatted')})",
                "spatial_compatibility": {
                    "same_path_row": True,
                    "same_crs": True,
                    "bands_available": True
                }
            })

    if valid_pairs:
        # Priority 6: Ranking:
        # 1. Same satellite first (True before False)
        # 2. Minimal positive interval (closest chronological revisit)
        # 3. Most recent monitoring date
        valid_pairs.sort(key=lambda p: (
            0 if p["same_satellite"] else 1,
            p["interval_days"],
            -p["before"].get("date_int", 0)
        ))

        bi_temporal_pairs = [valid_pairs[0]]

    # --------------------------------------------------
    # Detect Optical + SAR Multimodal Pairs
    # --------------------------------------------------
    optical_scenes = [
        s for s in scenes
        if s.get("modality") == "optical"
        and not s.get("is_generic_image")
        and (s.get("available_analyses", {}).get("ndvi") or s.get("available_analyses", {}).get("multispectral") or "B4" in s.get("bands", []))
        and s.get("date_int", 0) > 0
    ]

    sar_scenes = [
        s for s in scenes
        if s.get("modality") == "sar"
        or s.get("available_analyses", {}).get("sar_dual_pol")
        or s.get("scene_id", "").startswith("S1")
    ]

    multimodal_pairs = []
    if optical_scenes and sar_scenes:
        import rasterio
        from rasterio.warp import transform_bounds

        scene_wgs_cache = {}
        for s in optical_scenes + sar_scenes:
            s_id = s["scene_id"]
            if s_id in scene_wgs_cache:
                continue
            s_files = [f for f in files if f.get("scene_id") == s_id and f.get("path")]
            if not s_files:
                continue
            try:
                with rasterio.open(s_files[0]["path"]) as ds:
                    if ds.gcps and ds.gcps[0]:
                        gcps = ds.gcps[0]
                        lons = [g.x for g in gcps]
                        lats = [g.y for g in gcps]
                        scene_wgs_cache[s_id] = (min(lons), min(lats), max(lons), max(lats))
                    elif ds.crs and str(ds.crs) != "None":
                        scene_wgs_cache[s_id] = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
                    else:
                        scene_wgs_cache[s_id] = None
            except Exception:
                scene_wgs_cache[s_id] = None

        DEFAULT_BENCHMARK_SCENES = {
            "LC08_L2SP_009012_20260720_20260725_02_T1",
            "LC08_L2SP_138045_20260117_20260122_02_T1",
            "LC08_L2SP_139041_20260414_20260423_02_T1",
            "LC09_L2SP_141040_20260810_20260811_02_T1",
            "LC09_L2SP_141040_20260826_20260827_02_T1",
            "S1A_IW_GRDH_1SDV_20260810"
        }

        for opt in optical_scenes:
            opt_id = opt["scene_id"]
            opt_wgs = scene_wgs_cache.get(opt_id)

            for sar in sar_scenes:
                sar_id = sar["scene_id"]
                sar_wgs = scene_wgs_cache.get(sar_id)

                spatially_overlapping = False
                overlap_lon = 0.0
                overlap_lat = 0.0

                if opt_wgs and sar_wgs:
                    overlap_lon = max(0.0, min(opt_wgs[2], sar_wgs[2]) - max(opt_wgs[0], sar_wgs[0]))
                    overlap_lat = max(0.0, min(opt_wgs[3], sar_wgs[3]) - max(opt_wgs[1], sar_wgs[1]))
                    if overlap_lon > 0.01 and overlap_lat > 0.01:
                        spatially_overlapping = True
                elif opt.get("path_row") and sar.get("path_row") and opt.get("path_row") == sar.get("path_row"):
                    spatially_overlapping = True

                if not spatially_overlapping:
                    continue

                d_opt_int = opt.get("date_int", 0)
                d_sar_int = sar.get("date_int", 0)
                temporal_gap_days = 0
                if d_opt_int and d_sar_int:
                    try:
                        dt_opt = datetime.strptime(str(d_opt_int), "%Y%m%d")
                        dt_sar = datetime.strptime(str(d_sar_int), "%Y%m%d")
                        temporal_gap_days = abs((dt_opt - dt_sar).days)
                    except Exception:
                        temporal_gap_days = 0

                # Temporal tolerance: 30 days
                if temporal_gap_days > 30:
                    continue

                # Derive location
                location = "Regional Observation"
                pr = opt.get("path_row")
                if pr in {"134052", "134/052"}:
                    location = "Port Blair"
                elif opt_wgs and (92.0 <= (opt_wgs[0] + opt_wgs[2]) / 2 <= 93.5) and (11.0 <= (opt_wgs[1] + opt_wgs[3]) / 2 <= 13.5):
                    location = "Port Blair"
                elif pr in {"141040", "141/040"}:
                    location = "Northern Plains"
                elif pr in {"138045", "138/045"}:
                    location = "Sundarbans"
                elif pr in {"139041", "139/041"}:
                    location = "Varanasi Region"
                elif opt.get("path_row_formatted"):
                    location = f"WRS-2 {opt.get('path_row_formatted')}"

                pair_id = f"optsar_{opt_id}_{sar_id}"
                is_custom = (opt_id not in DEFAULT_BENCHMARK_SCENES or sar_id not in DEFAULT_BENCHMARK_SCENES)

                multimodal_pairs.append({
                    "pair_id": pair_id,
                    "pair_type": "optical_sar",
                    "location": location,
                    "optical_scene_id": opt_id,
                    "sar_scene_id": sar_id,
                    "optical_scene": opt,
                    "sar_scene": sar,
                    "optical_satellite": opt.get("satellite", "Landsat-9"),
                    "sar_satellite": sar.get("satellite", "Sentinel-1A"),
                    "optical_acquisition_date": opt.get("acquisition_date") or opt.get("date"),
                    "sar_acquisition_date": sar.get("acquisition_date") or sar.get("date"),
                    "temporal_gap_days": temporal_gap_days,
                    "spatial_overlap": True,
                    "overlap_degrees": {
                        "longitude": round(overlap_lon, 3),
                        "latitude": round(overlap_lat, 3)
                    },
                    "status": "compatible",
                    "detection_method": "Geographic Bounding Box Intersection (WGS84)",
                    "optical_preview": opt.get("thumbnail_url") or opt.get("thumbnail"),
                    "sar_preview": sar.get("thumbnail_url") or sar.get("thumbnail"),
                    "optical_bands": opt.get("bands", []),
                    "sar_polarizations": sar.get("bands", []),
                    "is_custom": is_custom
                })

        multimodal_pairs.sort(key=lambda p: (
            0 if p.get("is_custom") else 1,
            p["temporal_gap_days"],
            -p["optical_scene"].get("date_int", 0)
        ))

    # --------------------------------------------------
    # Determine input type
    # A. SINGLE OPTICAL/MULTISPECTRAL REMOTE-SENSING INPUT (single_scene)
    # B. SINGLE IMAGE VQA INPUT (single_image_vqa)
    # C. BI-TEMPORAL REMOTE-SENSING INPUT (bi_temporal_pair)
    # D. OPTICAL + SAR INPUT (optical_sar_fusion)
    # --------------------------------------------------

    has_optical = any(f.get("modality") == "optical" and not f.get("is_generic_image") for f in files)
    has_sar = any(f.get("modality") == "sar" for f in files)

    if len(bi_temporal_pairs) > 0:
        input_type = "bi_temporal_pair"

    elif has_optical and has_sar:
        input_type = "optical_sar_fusion"

    elif len(scenes) == 1:
        if scenes[0].get("is_generic_image"):
            input_type = "single_image_vqa"
        else:
            input_type = "single_scene"

    elif len(scenes) > 1 and all(s.get("is_generic_image") for s in scenes):
        input_type = "single_image_vqa"

    elif len(files) > 0:
        input_type = "image_collection"

    else:
        input_type = "no_input"

    DEFAULT_BENCHMARK_SCENES = {
        "LC08_L2SP_009012_20260720_20260725_02_T1",
        "LC08_L2SP_138045_20260117_20260122_02_T1",
        "LC08_L2SP_139041_20260414_20260423_02_T1",
        "LC09_L2SP_141040_20260810_20260811_02_T1",
        "LC09_L2SP_141040_20260826_20260827_02_T1",
        "S1A_IW_GRDH_1SDV_20260810"
    }

    # User-uploaded images and custom uploaded scenes appear at the top of the Sensor Catalog
    scenes.sort(key=lambda s: 0 if (s.get("is_generic_image") or s.get("scene_id") not in DEFAULT_BENCHMARK_SCENES) else 1)

    return {
        "success": True,
        "file_count": len(files),
        "scene_count": len(scenes),
        "input_type": input_type,
        "files": files,
        "scenes": scenes,
        "bi_temporal_pairs": bi_temporal_pairs,
        "multimodal_pairs": multimodal_pairs
    }