from pathlib import Path
import re
from datetime import datetime


# 1. ESA Bhoonidhi / Copernicus SAFE measurement GeoTIFF pattern
# Example: s1a-iw-grd-vv-20260413t120120-20260413t120145-064061-080f88-001.tiff
SAFE_SAR_PATTERN = re.compile(
    r"^(?P<sat>s1[ab])-(?P<mode>[a-z0-9]+)-(?P<type>[a-z0-9]+)-(?P<pol>vv|vh|hh|hv)-(?P<start>\d{8}t\d{6})-(?P<stop>\d{8}t\d{6})-(?P<orbit>\d{6})-(?P<datatake>[a-z0-9]{6})-\d{3}\.tiff?$",
    re.IGNORECASE
)

# 2. Standard benchmark SAR GeoTIFF pattern
# Example: S1A_IW_GRDH_1SDV_20260810_VV.TIF or PORT_BLAIR_SAR_VV.TIF
BENCH_SAR_PATTERN = re.compile(
    r"^(?P<scene>(?:S1[AB]_.+?|.+?_SAR))_(?P<pol>VV|VH|HH|HV)\.TIFF?$",
    re.IGNORECASE
)

# 3. Generic Sentinel-1 measurement pattern
# Example: s1a_iw_grd_vv_...
GENERIC_SAR_PATTERN = re.compile(
    r"^(?P<sat>s1[ab])[_-](?P<mode>[a-z0-9]+)[_-](?P<type>[a-z0-9]+)[_-](?P<pol>vv|vh|hh|hv)[_-](?P<rest>.+?)\.tiff?$",
    re.IGNORECASE
)


def parse_sar_filename(filename: str) -> dict | None:
    """
    Parse a Sentinel-1 SAR measurement raster filename.
    Extracts canonical product/acquisition identity, polarization (VV, VH),
    acquisition date, satellite platform, and mode.

    Guarantees that measurement files from the SAME Sentinel-1 acquisition
    (e.g., VV and VH from S1A_IW_GRDH_1SDV_20260413T120120_...SAFE)
    produce the EXACT SAME canonical scene_id.
    """
    name = Path(filename).name

    # Check ESA Bhoonidhi SAFE format
    m_safe = SAFE_SAR_PATTERN.match(name)
    if m_safe:
        sat_code = m_safe.group("sat").upper()
        sat_name = "Sentinel-1A" if sat_code == "S1A" else "Sentinel-1B"
        mode = m_safe.group("mode").upper()
        prod_type = m_safe.group("type").upper()
        pol = m_safe.group("pol").upper()
        start = m_safe.group("start").upper()
        orbit = m_safe.group("orbit")
        datatake = m_safe.group("datatake").upper()

        date_str = start[:8]
        date_formatted = None
        date_int = 0
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            date_formatted = dt.strftime("%d %b %Y")
            date_int = int(date_str)
        except Exception:
            date_formatted = date_str

        # Canonical acquisition identity shared by all polarizations of this product
        canonical_scene_id = f"{sat_code}_{mode}_{prod_type}_{date_str}_{orbit}"

        return {
            "matched": True,
            "scene_id": canonical_scene_id,
            "polarization": pol,
            "band": pol,
            "satellite": sat_name,
            "sensor": "C-SAR (Synthetic Aperture Radar)",
            "mode": mode,
            "product_type": prod_type,
            "date": date_formatted,
            "acquisition_date": date_formatted,
            "date_int": date_int,
            "date_str": date_str,
            "orbit": orbit,
            "datatake": datatake,
            "is_safe": True
        }

    # Check benchmark format
    m_bench = BENCH_SAR_PATTERN.match(name)
    if m_bench:
        scene_id = m_bench.group("scene")
        pol = m_bench.group("pol").upper()
        sat_name = "Sentinel-1A" if "S1A" in scene_id.upper() else ("Sentinel-1B" if "S1B" in scene_id.upper() else "Sentinel-1")

        date_str = None
        date_formatted = None
        date_int = 0
        for part in scene_id.split("_"):
            if len(part) >= 8 and part[:8].isdigit():
                date_str = part[:8]
                try:
                    dt = datetime.strptime(date_str, "%Y%m%d")
                    date_formatted = dt.strftime("%d %b %Y")
                    date_int = int(date_str)
                except Exception:
                    pass
                break

        return {
            "matched": True,
            "scene_id": scene_id,
            "polarization": pol,
            "band": pol,
            "satellite": sat_name,
            "sensor": "C-SAR (Synthetic Aperture Radar)",
            "mode": "IW",
            "product_type": "GRD",
            "date": date_formatted or "Active Scene",
            "acquisition_date": date_formatted or "Active Scene",
            "date_int": date_int,
            "date_str": date_str,
            "is_safe": False
        }

    # Check generic format
    m_gen = GENERIC_SAR_PATTERN.match(name)
    if m_gen:
        sat_code = m_gen.group("sat").upper()
        sat_name = "Sentinel-1A" if sat_code == "S1A" else "Sentinel-1B"
        mode = m_gen.group("mode").upper()
        prod_type = m_gen.group("type").upper()
        pol = m_gen.group("pol").upper()
        rest = m_gen.group("rest")

        # Extract date from rest if present
        date_m = re.search(r"(\d{8})", rest)
        date_str = date_m.group(1) if date_m else "UNKNOWN"
        date_formatted = None
        date_int = 0
        if date_str.isdigit() and len(date_str) == 8:
            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
                date_formatted = dt.strftime("%d %b %Y")
                date_int = int(date_str)
            except Exception:
                pass

        clean_rest = re.sub(r"-\d{3}$", "", rest)
        canonical_scene_id = f"{sat_code}_{mode}_{prod_type}_{clean_rest.upper()}"

        return {
            "matched": True,
            "scene_id": canonical_scene_id,
            "polarization": pol,
            "band": pol,
            "satellite": sat_name,
            "sensor": "C-SAR (Synthetic Aperture Radar)",
            "mode": mode,
            "product_type": prod_type,
            "date": date_formatted or "Active Scene",
            "acquisition_date": date_formatted or "Active Scene",
            "date_int": date_int,
            "date_str": date_str,
            "is_safe": False
        }

    return None


def is_sar_filename(filename: str) -> bool:
    """Return True if filename matches a known Sentinel-1 SAR pattern."""
    return parse_sar_filename(filename) is not None
