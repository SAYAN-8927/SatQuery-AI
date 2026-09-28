from dataclasses import dataclass
from typing import Callable

from app.tools.ndvi_analysis import run_ndvi_analysis
from app.tools.change_detection import run_change_detection
from app.tools.vlm_analysis import run_vlm_analysis
from app.tools.spectral_analysis import run_spectral_analysis
from app.tools.optical_sar_fusion import run_optical_sar_analysis
from app.tools.scene_metadata import extract_scene_metadata
from app.tools.unsupported_capability import handle_unsupported

@dataclass
class ToolDefinition:
    """
    Describes one analysis tool available to SatQuery.
    """

    name: str
    description: str
    status: str
    handler: Callable | None


TOOL_REGISTRY = {

    "ndvi_analysis": ToolDefinition(
        name="ndvi_analysis",
        description="Analyze vegetation using NDVI.",
        status="implemented",
        handler=run_ndvi_analysis
    ),

    "spectral_band_analysis": ToolDefinition(
        name="spectral_band_analysis",
        description="Analyze multispectral band reflectance and spectral signatures (B2, B3, B4, B5, NDWI, NDVI).",
        status="implemented",
        handler=run_spectral_analysis
    ),

    "remote_sensing_vlm": ToolDefinition(
        name="remote_sensing_vlm",
        description="Generate a remote-sensing scene description or VQA answer.",
        status="implemented",
        handler=run_vlm_analysis
    ),

    "change_detection_model": ToolDefinition(
    name="change_detection_model",
    description="Analyze changes between two images using NDVI difference.",
    status="implemented",
    handler=run_change_detection
    ),

    "optical_sar_model": ToolDefinition(
        name="optical_sar_model",
        description="Perform joint optical and SAR polarimetric backscatter analysis.",
        status="implemented",
        handler=run_optical_sar_analysis
    ),

    "scene_metadata_model": ToolDefinition(
        name="scene_metadata_model",
        description="Retrieve verified metadata (satellite, sensor, acquisition date, resolution, CRS) directly from active scene.",
        status="implemented",
        handler=extract_scene_metadata
    ),

    "unsupported_capability_handler": ToolDefinition(
        name="unsupported_capability_handler",
        description="Provide capability-aware response for requests outside Earth observation scope.",
        status="implemented",
        handler=handle_unsupported
    )
}


def get_tool(tool_name: str):

    return TOOL_REGISTRY.get(tool_name)


def list_tools():

    return list(TOOL_REGISTRY.values())