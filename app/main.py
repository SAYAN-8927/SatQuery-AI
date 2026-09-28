from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.images import router as image_router

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

app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "SatQuery AI Backend"
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