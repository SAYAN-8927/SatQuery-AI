from pathlib import Path
import rasterio


# File extensions that our application accepts
ALLOWED_EXTENSIONS = {
    ".tif",
    ".tiff",
    ".jpg",
    ".jpeg",
    ".png"
}


def validate_file_extension(filename: str):
    """
    Check whether the uploaded file has a supported extension.
    """

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return {
            "valid": False,
            "reason": "Unsupported file type."
        }

    return {
        "valid": True,
        "extension": extension
    }


def validate_tiff(file_path: Path):
    """
    Check whether a TIFF file can actually be opened
    as a raster dataset.
    """

    try:
        with rasterio.open(file_path) as dataset:

            crs_str = str(dataset.crs) if dataset.crs else None
            bounds_dict = {
                "left": dataset.bounds.left,
                "bottom": dataset.bounds.bottom,
                "right": dataset.bounds.right,
                "top": dataset.bounds.top
            }
            res_dict = {
                "x": dataset.res[0],
                "y": dataset.res[1]
            }
            has_gcps = False
            gcp_count = 0

            # Check for Ground Control Points (GCPs) in ESA Sentinel-1 SAFE GRD products
            if (not crs_str or crs_str == "None") and dataset.gcps:
                gcps, gcp_crs = dataset.gcps
                if gcp_crs:
                    crs_str = str(gcp_crs)
                if gcps:
                    has_gcps = True
                    gcp_count = len(gcps)
                    lons = [g.x for g in gcps]
                    lats = [g.y for g in gcps]
                    bounds_dict = {
                        "left": min(lons),
                        "bottom": min(lats),
                        "right": max(lons),
                        "top": max(lats)
                    }
                    # Default spatial pixel spacing for Sentinel-1 IW GRD is 10 m
                    res_dict = {"x": 10.0, "y": 10.0}

            return {
                "valid": True,
                "metadata": {
                    "width": dataset.width,
                    "height": dataset.height,
                    "bands": dataset.count,
                    "crs": crs_str or "None",
                    "bounds": bounds_dict,
                    "resolution": res_dict,
                    "dtype": str(dataset.dtypes[0]) if dataset.dtypes else "unknown",
                    "nodata": dataset.nodata,
                    "has_gcps": has_gcps,
                    "gcp_count": gcp_count
                }
            }

    except Exception:
        return {
            "valid": False,
            "reason": "The TIFF file could not be read as a valid raster."
        }