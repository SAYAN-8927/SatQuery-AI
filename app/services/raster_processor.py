from pathlib import Path
import rasterio
from rasterio.enums import Resampling
import numpy as np
import gc


def analyze_raster(file_path: Path):
    """
    Analyze a raster image and return useful
    information about its pixels and bands within strict 32 MB memory bounds.
    """
    try:
        with rasterio.Env(GDAL_CACHEMAX=32):
            with rasterio.open(file_path) as dataset:
                result = {
                    "data_type": dataset.dtypes[0],
                    "nodata": dataset.nodata,
                    "bands": []
                }

                # Analyze every band safely
                for band_number in range(1, dataset.count + 1):
                    try:
                        stats = dataset.statistics(
                            band_number,
                            approx=True
                        )
                        b_min, b_max, b_mean, b_std = stats.min, stats.max, stats.mean, stats.std
                    except Exception:
                        # Fallback using bounded 512x512 sample
                        sample = dataset.read(
                            band_number,
                            out_shape=(512, 512),
                            resampling=Resampling.nearest
                        ).astype(np.float32)

                        if dataset.nodata is not None:
                            valid = sample[sample != dataset.nodata]
                        elif np.any(sample > 0):
                            valid = sample[sample > 0]
                        else:
                            valid = sample.flatten()

                        if valid.size > 0:
                            b_min = float(np.min(valid))
                            b_max = float(np.max(valid))
                            b_mean = float(np.mean(valid))
                            b_std = float(np.std(valid))
                        else:
                            b_min, b_max, b_mean, b_std = 0.0, 0.0, 0.0, 0.0
                        del sample

                    result["bands"].append({
                        "band": band_number,
                        "min": float(b_min) if b_min is not None else 0.0,
                        "max": float(b_max) if b_max is not None else 0.0,
                        "mean": float(b_mean) if b_mean is not None else 0.0,
                        "stddev": float(b_std) if b_std is not None else 0.0
                    })

                gc.collect()
                return {
                    "success": True,
                    "analysis": result
                }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }