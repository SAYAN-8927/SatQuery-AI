from pathlib import Path
import rasterio


def analyze_raster(file_path: Path):
    """
    Analyze a raster image and return useful
    information about its pixels and bands.
    """

    try:
        with rasterio.open(file_path) as dataset:

            result = {
                "data_type": dataset.dtypes[0],
                "nodata": dataset.nodata,
                "bands": []
            }

            # Analyze every band
            for band_number in range(1, dataset.count + 1):

                stats = dataset.statistics(
                    band_number,
                    approx=True
                )

                result["bands"].append({
                    "band": band_number,
                    "min": stats.min,
                    "max": stats.max,
                    "mean": stats.mean,
                    "stddev": stats.std
                })

            return {
                "success": True,
                "analysis": result
            }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }