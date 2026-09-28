from pathlib import Path

from app.agent.tool_registry import get_tool


def execute_tool(
    tool_name: str,
    upload_dir: Path = Path("uploads"),
    output_dir: Path = Path("uploads/multispectral"),
    input_result: dict | None = None,
    query: str = "",
    target_scene_id: str | None = None,
    before_scene_id: str | None = None,
    after_scene_id: str | None = None,
    optical_scene_id: str | None = None,
    sar_scene_id: str | None = None,
    image_path: str | Path | None = None,
    active_scene: dict | None = None,
    active_pair_id: str | None = None,
    selected_scene_id: str | None = None
):
    tool = get_tool(tool_name)

    if tool is None:
        return {
            "success": False,
            "tool": tool_name,
            "error": "Tool is not registered."
        }

    if tool.status != "implemented":
        return {
            "success": False,
            "tool": tool_name,
            "status": tool.status,
            "error": f"Tool '{tool_name}' is not implemented yet."
        }

    if tool.handler is None:
        return {
            "success": False,
            "tool": tool_name,
            "error": "Tool has no execution handler."
        }

    try:

        # --------------------------------------------------
        # VLM scene description / visual Q&A
        # --------------------------------------------------

        if tool_name == "remote_sensing_vlm":
            return tool.handler(
                query=query,
                upload_dir=upload_dir,
                output_dir=output_dir,
                target_scene_id=target_scene_id,
                image_path=image_path
            )

        # --------------------------------------------------
        # Change detection requires a bi-temporal pair
        # --------------------------------------------------

        if tool_name == "change_detection_model":

            b_id = before_scene_id
            a_id = after_scene_id

            if not b_id or not a_id:
                return {
                    "success": False,
                    "tool": tool_name,
                    "error": "Change detection requires an explicitly selected compatible before/after scene pair. The current active input is a single scene."
                }

            return tool.handler(
                upload_dir=upload_dir,
                output_dir=Path("uploads/change_detection"),
                before_scene_id=b_id,
                after_scene_id=a_id
            )

        # --------------------------------------------------
        # Optical + SAR Fusion
        # --------------------------------------------------
        if tool_name == "optical_sar_model":
            opt_id = optical_scene_id or target_scene_id
            return tool.handler(
                upload_dir=upload_dir,
                output_dir=Path("uploads/fusion"),
                query=query,
                target_scene=opt_id,
                sar_scene=sar_scene_id,
                active_pair_id=active_pair_id
            )

        # --------------------------------------------------
        # Metadata Retrieval
        # --------------------------------------------------
        if tool_name == "scene_metadata_model":
            return tool.handler(
                upload_dir=upload_dir,
                target_scene_id=target_scene_id,
                input_result=input_result,
                active_scene=active_scene,
                active_pair_id=active_pair_id,
                selected_scene_id=selected_scene_id or target_scene_id
            )

        # --------------------------------------------------
        # Unsupported Capability
        # --------------------------------------------------
        if tool_name == "unsupported_capability_handler":
            return tool.handler(
                query=query
            )

        # --------------------------------------------------
        # Single-scene multispectral tools (NDVI, Spectral)
        # --------------------------------------------------
        if tool_name in {"ndvi_analysis", "spectral_band_analysis"}:
            return tool.handler(
                upload_dir=upload_dir,
                output_dir=output_dir,
                target_scene=target_scene_id
            )

        # --------------------------------------------------
        # Other registered tools
        # --------------------------------------------------

        return tool.handler(
            upload_dir=upload_dir,
            output_dir=output_dir
        )

    except Exception as e:
        return {
            "success": False,
            "tool": tool_name,
            "error": str(e)
        }