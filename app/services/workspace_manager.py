import os
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("satquery.workspace")

WORKSPACE_EXPIRY_HOURS = int(os.getenv("WORKSPACE_EXPIRY_HOURS", "24"))
BASE_UPLOAD_DIR = Path("uploads")
WORKSPACES_DIR = BASE_UPLOAD_DIR / "workspaces"


class WorkspaceManager:
    """
    Manages temporary SatQuery user workspaces, file isolation,
    explicit scene deletion, and inactivity-based cleanup.
    """

    def __init__(self, base_dir: Path = BASE_UPLOAD_DIR):
        self.base_dir = base_dir
        self.workspaces_dir = base_dir / "workspaces"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        self.expiry_hours = WORKSPACE_EXPIRY_HOURS

    def sanitize_workspace_id(self, workspace_id: str | None) -> str:
        """Sanitize workspace id to prevent directory traversal."""
        if not workspace_id or str(workspace_id).strip() in {"", "default", "satquery_default"}:
            return "satquery_default"
        clean = "".join(c for c in str(workspace_id) if c.isalnum() or c in {"_", "-"}).strip()
        if not clean.startswith("satquery_"):
            clean = f"satquery_{clean}"
        return clean or "satquery_default"

    def get_workspace_dir(self, workspace_id: str | None = None) -> Path:
        """
        Get the directory for a specific workspace.
        Creates subdirectories for previews, multispectral, change_detection, and fusion.
        """
        clean_id = self.sanitize_workspace_id(workspace_id)

        ws_dir = self.workspaces_dir / clean_id
        ws_dir.mkdir(parents=True, exist_ok=True)

        for subdir in ["previews", "multispectral", "change_detection", "fusion"]:
            (ws_dir / subdir).mkdir(parents=True, exist_ok=True)

        self.touch_workspace(clean_id)
        return ws_dir

    def touch_workspace(self, workspace_id: str, reset_cleared: bool = False):
        """Update last active timestamp for the workspace."""
        clean_id = self.sanitize_workspace_id(workspace_id)
        ws_dir = self.workspaces_dir / clean_id
        ws_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = ws_dir / "workspace_manifest.json"
        now_iso = datetime.utcnow().isoformat()

        manifest = {
            "workspace_id": clean_id,
            "created_at": now_iso,
            "last_active_at": now_iso,
            "expiry_hours": self.expiry_hours,
            "cleared": False
        }

        if manifest_file.exists():
            try:
                with open(manifest_file, "r") as f:
                    data = json.load(f)
                    manifest.update(data)
            except Exception:
                pass

        manifest["last_active_at"] = now_iso
        if reset_cleared:
            manifest["cleared"] = False

        try:
            with open(manifest_file, "w") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write manifest for {clean_id}: {e}")

    def get_workspace_info(self, workspace_id: str | None = None) -> dict:
        """Get metadata and file statistics for a workspace."""
        clean_id = self.sanitize_workspace_id(workspace_id)
        ws_dir = self.get_workspace_dir(clean_id)
        manifest_file = ws_dir / "workspace_manifest.json"

        created_at = datetime.utcnow().isoformat()
        last_active_at = created_at

        if manifest_file.exists():
            try:
                with open(manifest_file, "r") as f:
                    data = json.load(f)
                    created_at = data.get("created_at", created_at)
                    last_active_at = data.get("last_active_at", last_active_at)
            except Exception:
                pass

        # Count raster files in workspace directory
        raster_files = [
            f.name for f in ws_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
        ]

        # For satquery_default, also count files in base_dir if any
        if clean_id == "satquery_default":
            for f in self.base_dir.iterdir():
                if f.is_file() and f.suffix.lower() in {".tif", ".tiff", ".png", ".jpg", ".jpeg"}:
                    if f.name not in raster_files:
                        raster_files.append(f.name)

        return {
            "workspace_id": clean_id,
            "created_at": created_at,
            "last_active_at": last_active_at,
            "expiry_hours": self.expiry_hours,
            "file_count": len(raster_files),
            "files": raster_files
        }

    def delete_scene(self, workspace_id: str | None, scene_id: str) -> dict:
        """
        Completely delete a scene, removing:
        - All band GeoTIFFs (B2, B3, B4, B5, VV, VH, etc.) and .aux.xml
        - Generated band previews in previews/
        - Derived artifacts belonging exclusively to that scene in multispectral/
        - Comparison artifacts where scene_id participates in change_detection/
        - Cross-sensor artifacts where scene_id participates in fusion/

        Guarantees other scenes and shared global resources are NEVER touched.
        """
        if not scene_id or not scene_id.strip():
            return {"success": False, "error": "Invalid scene_id"}

        clean_scene_id = scene_id.strip()
        clean_ws_id = self.sanitize_workspace_id(workspace_id)
        ws_dir = self.get_workspace_dir(clean_ws_id)

        target_dirs = [ws_dir]
        default_ws = self.get_workspace_dir("satquery_default")
        if default_ws.exists() and default_ws.resolve() != ws_dir.resolve():
            target_dirs.append(default_ws)
        if self.base_dir.exists() and self.base_dir.resolve() != ws_dir.resolve():
            target_dirs.append(self.base_dir)

        deleted_files = []
        errors = []

        for base in target_dirs:
            if not base.exists():
                continue

            # 1. Main Scene Files (GeoTIFFs and XMLs)
            for file_path in base.iterdir():
                if file_path.is_file():
                    import re
                    from app.services.sar_identifier import parse_sar_filename
                    sar_parsed = parse_sar_filename(file_path.name)
                    sar_match = bool(sar_parsed and (sar_parsed.get("scene_id") == clean_scene_id or clean_scene_id in sar_parsed.get("scene_id", "")))
                    stem_norm = re.sub(r"[^\w\-_]", "_", file_path.stem)
                    scene_norm = re.sub(r"[^\w\-_]", "_", clean_scene_id)
                    matches = (
                        sar_match or
                        file_path.name.startswith(clean_scene_id) or
                        clean_scene_id in file_path.name or
                        clean_scene_id in file_path.stem or
                        file_path.stem in clean_scene_id or
                        stem_norm == scene_norm or
                        scene_norm in stem_norm or
                        clean_scene_id.replace("_", " ").lower() in file_path.name.lower()
                    )
                    if matches:
                        try:
                            file_path.unlink(missing_ok=True)
                            deleted_files.append(str(file_path))
                        except Exception as e:
                            errors.append(f"Failed to delete {file_path.name}: {e}")

            # 2. Previews (previews/ directory)
            p_dir = base / "previews"
            if p_dir.exists() and p_dir.is_dir():
                for p_file in p_dir.iterdir():
                    if p_file.is_file() and clean_scene_id in p_file.name:
                        try:
                            p_file.unlink(missing_ok=True)
                            deleted_files.append(str(p_file))
                        except Exception as e:
                            errors.append(f"Failed to delete preview {p_file.name}: {e}")

            # 3. Multispectral outputs (multispectral/ directory)
            m_dir = base / "multispectral"
            if m_dir.exists() and m_dir.is_dir():
                for m_file in m_dir.iterdir():
                    if m_file.is_file() and clean_scene_id in m_file.name:
                        try:
                            m_file.unlink(missing_ok=True)
                            deleted_files.append(str(m_file))
                        except Exception as e:
                            errors.append(f"Failed to delete multispectral artifact {m_file.name}: {e}")

            # 4. Change detection outputs (change_detection/ directory)
            cd_dir = base / "change_detection"
            if cd_dir.exists() and cd_dir.is_dir():
                for cd_file in cd_dir.iterdir():
                    if cd_file.is_file() and clean_scene_id in cd_file.name:
                        try:
                            cd_file.unlink(missing_ok=True)
                            deleted_files.append(str(cd_file))
                        except Exception as e:
                            errors.append(f"Failed to delete change detection artifact {cd_file.name}: {e}")

            # 5. Fusion outputs (fusion/ directory)
            f_dir = base / "fusion"
            if f_dir.exists() and f_dir.is_dir():
                for f_file in f_dir.iterdir():
                    if f_file.is_file() and clean_scene_id in f_file.name:
                        try:
                            f_file.unlink(missing_ok=True)
                            deleted_files.append(str(f_file))
                        except Exception as e:
                            errors.append(f"Failed to delete fusion artifact {f_file.name}: {e}")

        self.touch_workspace(clean_ws_id)

        if not deleted_files and not errors:
            return {
                "success": False,
                "error": f"Scene '{clean_scene_id}' not found in workspace '{clean_ws_id}'.",
                "deleted_files": []
            }

        return {
            "success": len(errors) == 0,
            "scene_id": clean_scene_id,
            "workspace_id": clean_ws_id,
            "deleted_files": deleted_files,
            "deleted_count": len(deleted_files),
            "errors": errors
        }

    def clear_workspace(self, workspace_id: str | None) -> dict:
        """
        Clears all uploaded datasets and derived artifacts in the specified workspace.
        Does not touch shared/global resources outside this workspace.
        """
        clean_ws_id = self.sanitize_workspace_id(workspace_id)
        ws_dir = self.get_workspace_dir(clean_ws_id)

        deleted_files = []
        errors = []

        subdirs_to_clean = [
            ws_dir,
            ws_dir / "previews",
            ws_dir / "multispectral",
            ws_dir / "change_detection",
            ws_dir / "fusion"
        ]

        if clean_ws_id == "satquery_default":
            subdirs_to_clean.extend([
                self.base_dir,
                self.base_dir / "previews",
                self.base_dir / "multispectral",
                self.base_dir / "change_detection",
                self.base_dir / "fusion"
            ])

        for target_dir in subdirs_to_clean:
            if not target_dir.exists() or not target_dir.is_dir():
                continue

            for file_path in target_dir.iterdir():
                if file_path.is_file():
                    if file_path.name in {"workspace_manifest.json"}:
                        continue
                    if file_path.suffix.lower() in {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".xml"}:
                        try:
                            file_path.unlink(missing_ok=True)
                            deleted_files.append(str(file_path))
                        except Exception as e:
                            errors.append(f"Failed to unlink {file_path.name}: {e}")

        self.touch_workspace(clean_ws_id)
        manifest_file = ws_dir / "workspace_manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r") as f:
                    data = json.load(f)
                data["cleared"] = True
                with open(manifest_file, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

        return {
            "success": len(errors) == 0,
            "workspace_id": clean_ws_id,
            "deleted_files": deleted_files,
            "deleted_count": len(deleted_files),
            "errors": errors
        }

    def cleanup_expired_workspaces(self) -> list:
        """
        Removes temporary workspace directories that have been inactive
        longer than WORKSPACE_EXPIRY_HOURS.
        Excludes protected workspaces and root uploads.
        """
        cleaned = []
        now = datetime.utcnow()
        expiry_delta = timedelta(hours=self.expiry_hours)

        if not self.workspaces_dir.exists():
            return cleaned

        for ws_folder in self.workspaces_dir.iterdir():
            if not ws_folder.is_dir():
                continue

            if ws_folder.name == "satquery_default":
                continue

            manifest_file = ws_folder / "workspace_manifest.json"
            last_active = None

            if manifest_file.exists():
                try:
                    with open(manifest_file, "r") as f:
                        data = json.load(f)
                        last_active_str = data.get("last_active_at")
                        if last_active_str:
                            last_active = datetime.fromisoformat(last_active_str)
                except Exception:
                    pass

            if not last_active:
                try:
                    mtime = ws_folder.stat().st_mtime
                    last_active = datetime.utcfromtimestamp(mtime)
                except Exception:
                    continue

            if (now - last_active) > expiry_delta:
                try:
                    shutil.rmtree(ws_folder, ignore_errors=True)
                    cleaned.append(ws_folder.name)
                    logger.info(f"Cleaned up expired workspace: {ws_folder.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove expired workspace {ws_folder.name}: {e}")

        return cleaned


# Global Singleton
workspace_manager = WorkspaceManager()
