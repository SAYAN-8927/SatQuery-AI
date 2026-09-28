import os
import sys

def run_checks():
    print("=" * 60)
    print("TESTING DEPLOYMENT-AWARE VLM ARCHITECTURE")
    print("=" * 60)

    # 1. LOCAL CHECK
    if "RENDER" in os.environ:
        del os.environ["RENDER"]
    if "ENABLE_LOCAL_VLM" in os.environ:
        del os.environ["ENABLE_LOCAL_VLM"]

    from app.tools.vlm_analysis import is_local_vlm_enabled, run_vlm_analysis
    local_val = is_local_vlm_enabled()
    print(f"[CHECK 1] Local development is_local_vlm_enabled(): {local_val}")
    assert local_val is True, f"Expected True locally, got {local_val}"

    # 2. SIMULATED RENDER CHECK
    os.environ["RENDER"] = "true"
    render_val = is_local_vlm_enabled()
    print(f"[CHECK 2] Render environment is_local_vlm_enabled(): {render_val}")
    assert render_val is False, f"Expected False on Render, got {render_val}"

    # Verify VLM query on Render does NOT load torch or transformers
    assert "torch" not in sys.modules, "torch was prematurely loaded!"
    assert "transformers" not in sys.modules, "transformers was prematurely loaded!"
    assert "peft" not in sys.modules, "peft was prematurely loaded!"

    res_render = run_vlm_analysis(
        query="Can you describe what is visible here?",
        target_scene_id="LC09_L2SP_141040_20260826_20260827_02_T1"
    )

    print(f"[CHECK 3] Render VLM success: {res_render.get('success')}")
    print(f"[CHECK 3] Render VLM deployment_constrained: {res_render.get('deployment_constrained')}")
    print(f"[CHECK 3] Render VLM vlm_available: {res_render.get('vlm_available')}")
    print(f"[CHECK 3] Render VLM answer:\n    {res_render.get('answer')}")

    assert res_render.get("success") is True, "Expected success=True"
    assert res_render.get("deployment_constrained") is True, "Expected deployment_constrained=True"
    assert res_render.get("vlm_available") is False, "Expected vlm_available=False"

    # Confirm PyTorch and transformers were NEVER imported
    print(f"[CHECK 4] torch in sys.modules: {'torch' in sys.modules}")
    print(f"[CHECK 4] transformers in sys.modules: {'transformers' in sys.modules}")
    print(f"[CHECK 4] peft in sys.modules: {'peft' in sys.modules}")
    assert "torch" not in sys.modules, "torch should NOT be imported on Render path!"
    assert "transformers" not in sys.modules, "transformers should NOT be imported on Render path!"
    assert "peft" not in sys.modules, "peft should NOT be imported on Render path!"

    # 3. END-TO-END CONTROLLER TEST UNDER SIMULATED RENDER
    print("\n[CHECK 5] Testing End-to-End Query Controller under simulated Render...")
    from app.agent.controller import process_user_query

    # VLM direct query under Render
    query_vlm = process_user_query(
        query="Can you describe what is visible here?",
        scene_id="LC09_L2SP_141040_20260826_20260827_02_T1",
        mode="single_scene"
    )
    print(f"  • VLM Query Success: {query_vlm.get('success')}")
    print(f"  • Headline: {query_vlm.get('interpretation', {}).get('headline')}")
    print(f"  • Trace Tool Execution Details: {query_vlm.get('execution_trace', {}).get('steps', [])[-1].get('details')}")
    assert query_vlm.get("success") is True
    assert "VLM Offline" in query_vlm.get("interpretation", {}).get("headline", "")

    # Scientific NDVI query under Render (must execute without VLM crash)
    query_ndvi = process_user_query(
        query="Calculate NDVI and explain the vegetation.",
        scene_id="LC09_L2SP_141040_20260826_20260827_02_T1",
        mode="single_scene"
    )
    m_ndvi = query_ndvi.get("analysis", {}).get("ndvi_statistics", {}).get("mean_ndvi")
    print(f"  • NDVI Scientific Execution under Render: Mean NDVI = {m_ndvi}")
    assert m_ndvi is not None, "NDVI calculation should have succeeded!"
    print(f"  • torch still absent after scientific execution: {'torch' not in sys.modules}")
    assert "torch" not in sys.modules, "torch should still be absent!"

    # 4. RESTORE LOCAL AND VERIFY LOCAL VLM CAN STILL BE INVOKED
    print("\n[CHECK 6] Restoring Local environment and verifying local VLM capability...")
    del os.environ["RENDER"]
    local_val2 = is_local_vlm_enabled()
    print(f"  • Restored is_local_vlm_enabled(): {local_val2}")
    assert local_val2 is True

    # Invoke local VLM
    res_local = run_vlm_analysis(
        query="Is there vegetation in this image? Answer concisely.",
        target_scene_id="LC09_L2SP_141040_20260826_20260827_02_T1"
    )
    print(f"  • Local VLM Success: {res_local.get('success')}")
    print(f"  • Local VLM Answer: {res_local.get('answer')}")
    print(f"  • Local Device: {res_local.get('model_metadata', {}).get('device')}")
    assert res_local.get("success") is True
    assert len(res_local.get("answer", "")) > 0
    assert "torch" in sys.modules, "torch should now be loaded locally!"

    print("\n" + "=" * 60)
    print("ALL DEPLOYMENT-AWARE VLM VALIDATION CHECKS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_checks()
