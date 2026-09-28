import os
import sys
import time
import threading

def get_current_rss_mb() -> float:
    """Return process RSS in MB using /proc/self/status on Linux or psutil/resource."""
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / 1024.0
    except Exception:
        pass
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024.0 * 1024.0)
    except Exception:
        pass
    try:
        import resource
        scale = 1024.0 if sys.platform != "darwin" else (1024.0 * 1024.0)
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / scale
    except Exception:
        pass
    return 0.0

print(f"[MEMORY] startup: {get_current_rss_mb():.2f} MB", flush=True)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.images import router as image_router

print(f"[MEMORY] after_imports: {get_current_rss_mb():.2f} MB", flush=True)

# Lightweight background memory reporter (every 10s)
def _background_memory_reporter():
    start_time = time.time()
    logged_30 = False
    logged_60 = False
    logged_120 = False
    while True:
        time.sleep(10)
        elapsed = time.time() - start_time
        rss = get_current_rss_mb()
        print(f"[MEMORY] periodic_rss: {rss:.2f} MB (elapsed: {int(elapsed)}s)", flush=True)
        if not logged_30 and elapsed >= 30:
            print(f"[MEMORY] idle_30s: {rss:.2f} MB", flush=True)
            logged_30 = True
        if not logged_60 and elapsed >= 60:
            print(f"[MEMORY] idle_60s: {rss:.2f} MB", flush=True)
            logged_60 = True
        if not logged_120 and elapsed >= 120:
            print(f"[MEMORY] idle_120s: {rss:.2f} MB", flush=True)
            logged_120 = True

threading.Thread(target=_background_memory_reporter, daemon=True).start()

app = FastAPI(
    title="SatQuery AI",
    description="Agentic Vision-Language Assistant for Remote Sensing",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def memory_logging_middleware(request: Request, call_next):
    path = request.url.path
    if path == "/api/scenes":
        print(f"[MEMORY] before_scenes: {get_current_rss_mb():.2f} MB", flush=True)
    elif path == "/api/examples":
        print(f"[MEMORY] before_examples: {get_current_rss_mb():.2f} MB", flush=True)

    before_rss = get_current_rss_mb()
    response = await call_next(request)
    after_rss = get_current_rss_mb()

    if any(path.startswith(p) for p in ["/api/health", "/api/scenes", "/api/examples", "/api/query", "/api/images/upload"]):
        print(f"[MEMORY] endpoint={path} before={before_rss:.2f}MB after={after_rss:.2f}MB", flush=True)

    if path == "/api/scenes":
        print(f"[MEMORY] after_scenes: {after_rss:.2f} MB", flush=True)
    elif path == "/api/examples":
        print(f"[MEMORY] after_examples: {after_rss:.2f} MB", flush=True)

    return response

app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)

@app.get("/api/health")
def health_check():
    from app.tools.vlm_analysis import is_local_vlm_enabled
    vlm_enabled = is_local_vlm_enabled()
    return {
        "status": "ok",
        "service": "SatQuery AI Backend",
        "vlm_enabled": vlm_enabled,
        "runtime_environment": "local_gpu" if vlm_enabled else "render_cloud",
        "device": "NVIDIA GTX 1650 (FP16)" if vlm_enabled else "Cloud VLM Bypassed"
    }


app.include_router(image_router)

from pathlib import Path
from fastapi.responses import FileResponse

dist_dir = Path("frontend/dist")
if dist_dir.exists():
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    @app.get("/dashboard")
    def serve_frontend():
        return FileResponse(
            dist_dir / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )