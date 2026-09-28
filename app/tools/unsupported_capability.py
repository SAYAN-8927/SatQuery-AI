from typing import Any, Dict


def handle_unsupported(
    query: str = "",
    **kwargs
) -> Dict[str, Any]:
    """
    Handle unsupported capability queries (e.g. weather forecasting, stock prediction)
    with a clear, capability-aware response rather than invoking VLM hallucinations.
    """
    q_lower = (query or "").lower()

    if any(k in q_lower for k in ["weather", "forecast", "tomorrow", "rain", "temperature"]):
        message = (
            "Weather forecasting and future meteorological predictions are not supported by SatQuery. "
            "SatQuery is an Earth observation analysis engine designed for multispectral, radar, and visual "
            "analysis of acquired satellite observations. The selected satellite imagery cannot provide tomorrow's forecast."
        )
    else:
        message = (
            "This capability is not supported by SatQuery. SatQuery AI provides calibrated Earth observation "
            "analysis, including vegetation indexing (NDVI), water delineation (NDWI), bi-temporal change detection, "
            "optical + SAR cross-sensor fusion, and remote sensing visual interpretation."
        )

    return {
        "success": True,
        "tool": "unsupported_capability_handler",
        "supported": False,
        "query": query,
        "message": message
    }
