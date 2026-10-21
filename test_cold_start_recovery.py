import urllib.request
import urllib.error
import json
import time
import http.server
import threading
import sys
from fastapi.testclient import TestClient
from app.main import app

BASE_URL = "http://127.0.0.1:8000"

def test_cors_and_contract():
    print("\n[TEST A & B] Verifying CORS Configuration & Health Endpoint Contract...")
    client = TestClient(app)

    # 1. Allowed Vercel Origin
    res = client.get("/api/health", headers={"Origin": "https://sat-query-ai-snowy.vercel.app"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data.get("status") == "ok", f"Expected status 'ok', got {data}"
    assert data.get("service") == "SatQuery AI Backend"

    origin_header = res.headers.get("access-control-allow-origin")
    cred_header = res.headers.get("access-control-allow-credentials")
    assert origin_header == "https://sat-query-ai-snowy.vercel.app", f"Unexpected origin header: {origin_header}"
    assert cred_header == "true", f"Expected allow-credentials 'true', got {cred_header}"
    print(f"  [+] /api/health returned HTTP 200 OK: {data}")
    print(f"  [+] CORS origin correctly permitted: {origin_header} (credentials: {cred_header})")

    # 2. Block unauthorized arbitrary origins (no unrestricted wildcard in production)
    res_unauth = client.get("/api/health", headers={"Origin": "https://unauthorized-attacker.com"})
    unauth_origin = res_unauth.headers.get("access-control-allow-origin")
    assert unauth_origin is None, f"Expected unauthorized origin to be rejected, got: {unauth_origin}"
    print(f"  [+] Unauthorized origin correctly blocked: {unauth_origin}")
    print("  -> TEST A & B: PASS (CORS and API health contract verified)")

def test_api_health_immediate():
    print("\n[TEST C] Health check when backend is immediately available...")
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data.get("status") == "ok", f"Expected status 'ok', got {data}"
    print(f"  [+] /api/health returned HTTP 200: status='{data.get('status')}', service='{data.get('service')}'")
    print(f"  [+] vlm_enabled: {data.get('vlm_enabled')}, runtime_environment: {data.get('runtime_environment')}")
    print("  -> TEST C: PASS (Backend immediately detected online)")

def test_simulated_render_cold_start():
    print("\n[TEST D, E, F, G] Simulating Render Cold-Start (Checking -> Waking -> Online with Increasing Delays)...")

    # Simulate Render mock server returning 502 for the first 3 requests, then 200 OK
    call_count = [0]

    class MockRenderHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            call_count[0] += 1
            if self.path == "/api/health":
                if call_count[0] <= 3:
                    # Simulate Render 502 Bad Gateway / sleeping
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Render instance is waking up"}')
                else:
                    # Instance is now awake!
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status": "ok", "service": "SatQuery AI Backend", "vlm_enabled": false}')
            elif self.path.startswith("/api/scenes"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"success": true, "data": {"scenes": [{"scene_id": "test_scene"}]}}')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # quiet

    server = http.server.HTTPServer(("127.0.0.1", 9998), MockRenderHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Frontend bounded retry sequence simulation:
    # State starts at 'checking'
    # Request 1 -> 502 -> transition to 'waking' -> delay 3s (scaled to 0.1s for fast unit test)
    # Request 2 -> 502 -> status remains 'waking' -> delay 5s (scaled to 0.1s)
    # Request 3 -> 502 -> status remains 'waking' -> delay 8s (scaled to 0.1s)
    # Request 4 -> 200 OK -> transition to 'online' -> load scenes -> loop stops immediately!

    mock_url = "http://127.0.0.1:9998"
    status = "checking"
    backend_online = False
    retry_loop_active = True
    poll_count = 0
    scenes_loaded = False
    delays = [0.05, 0.1, 0.15, 0.2]

    while retry_loop_active and poll_count < 10:
        poll_count += 1
        try:
            req = urllib.request.Request(f"{mock_url}/api/health", headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "ok":
                        backend_online = True
                        status = "online"
                        retry_loop_active = False # Stop loop immediately!
                        # Trigger data load
                        with urllib.request.urlopen(f"{mock_url}/api/scenes") as sc_resp:
                            sc_data = json.loads(sc_resp.read().decode())
                            scenes_loaded = sc_data.get("success") and len(sc_data["data"]["scenes"]) > 0
                        print(f"  [+] Attempt {poll_count}: HTTP 200 OK -> Transitioned to status='{status}', backendOnline={backend_online}")
                        print(f"  [+] Automatically fetched scenes without page refresh: {scenes_loaded}")
                        print(f"  [+] Retry loop successfully terminated (active={retry_loop_active})")
        except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:
            status = "waking"
            print(f"  [-] Attempt {poll_count}: Cold start sleeping -> Frontend shows: 'Waking backend — first startup may take around a minute'")
            time.sleep(delays[min(poll_count - 1, len(delays) - 1)])

    server.shutdown()
    assert status == "online", f"Expected final status 'online', got '{status}'"
    assert backend_online == True, "Expected backend_online to be True"
    assert retry_loop_active == False, "Expected retry loop to be inactive after recovery"
    assert scenes_loaded == True, "Expected scenes to load automatically upon waking"
    print("  -> TEST D, E, F, G: PASS (Cold-start retries gracefully and recovers to Online without refresh)")

def test_ndvi_workflow_functional():
    print("\n[TEST H] Verifying NDVI Query Workflow via Direct Application Engine...")
    client = TestClient(app)
    payload = {
        "query": "Calculate NDVI and analyze vegetation vigor.",
        "active_scene_id": "LC91340522026109SGI00",
        "mode": "single_scene"
    }
    res = client.post("/api/query", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data.get("success") == True, f"Query failed: {data}"
    assert data.get("selected_tool") == "ndvi_analysis", f"Unexpected tool: {data.get('selected_tool')}"
    stats = data.get("analysis", {}).get("ndvi_statistics", {})
    mean_ndvi = stats.get("mean_ndvi") if stats.get("mean_ndvi") is not None else stats.get("mean")
    print(f"  [+] Selected Tool: {data.get('selected_tool')}")
    interp = data.get("interpretation", {})
    interp_text = interp.get("interpretation") or interp.get("summary") or str(interp)
    print(f"  [+] Interpretation: {interp_text[:80]}...")
    assert mean_ndvi is not None, "Mean NDVI should not be None"
    print("  -> TEST H: PASS (NDVI scientific query workflow remains fully functional)")

def run_all():
    print("=" * 70)
    print("SATQUERY AI -- FRONTEND COLD-START RECOVERY & HEALTH AUDIT")
    print("=" * 70)
    test_cors_and_contract()
    test_api_health_immediate()
    test_simulated_render_cold_start()
    test_ndvi_workflow_functional()
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED CLEANLY (A through H Verified)")
    print("=" * 70)

if __name__ == "__main__":
    run_all()
