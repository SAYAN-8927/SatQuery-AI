from pathlib import Path


def classify_image(filename: str, metadata: dict | None = None):
    """
    Classify the uploaded image based on the information
    currently available to the backend.

    This is NOT an AI classifier yet.
    It is a first-stage classifier.
    """

    extension = Path(filename).suffix.lower()

    # TIFF / GeoTIFF
    if extension in {".tif", ".tiff"}:

        if metadata is None:
            return {
                "type": "unknown",
                "confidence": 0.0,
                "reason": "TIFF metadata is not available."
            }

        # A TIFF that has CRS information is geospatial raster data.
        if metadata.get("crs") and metadata.get("crs") != "None":
            from app.services.band_identifier import identify_landsat_band
            band_info = identify_landsat_band(filename)
            if band_info.get("identified"):
                return {
                    "type": "remote_sensing",
                    "modality": "optical",
                    "satellite": band_info.get("satellite", "Landsat-9"),
                    "band": band_info.get("band"),
                    "confidence": 0.98,
                    "reason": f"Calibrated {band_info.get('satellite')} band ({band_info.get('name')}) with valid geospatial CRS."
                }

            from app.services.sar_identifier import parse_sar_filename
            sar_info = parse_sar_filename(filename)
            if sar_info:
                return {
                    "type": "remote_sensing",
                    "modality": "sar",
                    "satellite": sar_info.get("satellite", "Sentinel-1"),
                    "band": sar_info.get("polarization"),
                    "confidence": 0.98,
                    "reason": f"Calibrated {sar_info.get('satellite', 'Sentinel-1')} SAR raster ({sar_info.get('polarization')}) with valid geospatial CRS."
                }

            is_single = metadata.get("bands") == 1
            return {
                "type": "remote_sensing",
                "modality": "optical" if is_single else "raster",
                "confidence": 0.95,
                "reason": "Single-band calibrated scientific GeoTIFF with geospatial CRS." if is_single else "TIFF contains geospatial CRS information."
            }

        return {
            "type": "raster",
            "modality": "unknown",
            "confidence": 0.70,
            "reason": "Valid TIFF raster, but geospatial CRS was not detected."
        }

    # JPEG / PNG
    if extension in {".jpg", ".jpeg", ".png"}:
        return {
            "type": "image",
            "modality": "unknown",
            "confidence": 0.0,
            "reason": "Visual content classification is required."
        }

    return {
        "type": "unknown",
        "confidence": 0.0,
        "reason": "Unsupported image format."
    }