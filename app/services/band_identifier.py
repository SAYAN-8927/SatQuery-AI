from pathlib import Path
import re


LANDSAT_BANDS = {
    "B1": {
        "name": "Coastal Aerosol",
        "wavelength_um": "0.43-0.45",
        "resolution_m": 30
    },
    "B2": {
        "name": "Blue",
        "wavelength_um": "0.45-0.51",
        "resolution_m": 30
    },
    "B3": {
        "name": "Green",
        "wavelength_um": "0.53-0.59",
        "resolution_m": 30
    },
    "B4": {
        "name": "Red",
        "wavelength_um": "0.64-0.67",
        "resolution_m": 30
    },
    "B5": {
        "name": "Near Infrared",
        "wavelength_um": "0.85-0.88",
        "resolution_m": 30
    },
    "B6": {
        "name": "SWIR 1",
        "wavelength_um": "1.57-1.65",
        "resolution_m": 30
    },
    "B7": {
        "name": "SWIR 2",
        "wavelength_um": "2.11-2.29",
        "resolution_m": 30
    },
    "B8": {
        "name": "Panchromatic",
        "wavelength_um": "0.50-0.68",
        "resolution_m": 15
    },
    "B9": {
        "name": "Cirrus",
        "wavelength_um": "1.36-1.38",
        "resolution_m": 30
    },
    "B10": {
        "name": "Thermal Infrared 1 (TIRS 1)",
        "wavelength_um": "10.60-11.19",
        "resolution_m": 100
    },
    "B11": {
        "name": "Thermal Infrared 2 (TIRS 2)",
        "wavelength_um": "11.50-12.51",
        "resolution_m": 100
    }
}


def identify_landsat_band(filename: str):
    """
    Identify the Landsat band and satellite platform from a Landsat filename.
    Supports both USGS Collection 2 Level-2 Surface Reflectance (e.g. ..._SR_B2.TIF)
    and standard USGS / ISRO Level-1/2 single-band GeoTIFFs (e.g. LC91340522026109SGI00_B2.TIF).
    """

    name = Path(filename).name.upper()

    # Look for patterns such as SR_B4, _B2, _B5, _SR_B2, etc.
    match = re.search(r"(?:^|[_.-])(?:SR_)?(B(?:[1-9]|1[0-1]))(?:\.TIF|\.TIFF|_|$)", name, re.IGNORECASE)

    if not match:
        return {
            "identified": False,
            "reason": "Could not identify a Landsat band."
        }

    band_code = match.group(1).upper()

    band_info = LANDSAT_BANDS.get(band_code)

    if band_info is None:
        return {
            "identified": False,
            "reason": f"Band {band_code} is not supported."
        }

    # Identify satellite platform from standard prefix
    if name.startswith("LC09") or name.startswith("LC9"):
        satellite = "Landsat-9"
    elif name.startswith("LC08") or name.startswith("LC8"):
        satellite = "Landsat-8"
    elif name.startswith("LE07") or name.startswith("LE7"):
        satellite = "Landsat-7"
    elif name.startswith("LT05") or name.startswith("LT5"):
        satellite = "Landsat-5"
    else:
        satellite = "Landsat 8/9"

    is_sr = "_SR_" in name or name.startswith("SR_")

    return {
        "identified": True,
        "satellite": satellite,
        "product": "Collection 2 Level-2 Surface Reflectance" if is_sr else "Landsat Calibrated Single-Band GeoTIFF",
        "band": band_code,
        "name": band_info["name"],
        "wavelength_um": band_info["wavelength_um"],
        "resolution_m": band_info["resolution_m"]
    }