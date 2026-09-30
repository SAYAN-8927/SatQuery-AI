import type {
  SceneData,
  ExampleQuery,
  QueryResult,
  UploadResponse,
  QueryPayload,
  DeleteSceneResponse,
  WorkspaceInfo,
} from './types';

const WORKSPACE_STORAGE_KEY = 'satquery_workspace_id';

export function getOrCreateWorkspaceId(): string {
  try {
    let wsId = localStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (!wsId || !wsId.trim()) {
      const rand = Math.random().toString(36).substring(2, 10);
      wsId = `satquery_${rand}`;
      localStorage.setItem(WORKSPACE_STORAGE_KEY, wsId);
    }
    return wsId;
  } catch {
    return 'satquery_default';
  }
}

export function resetWorkspaceId(): string {
  const rand = Math.random().toString(36).substring(2, 10);
  const wsId = `satquery_${rand}`;
  try {
    localStorage.setItem(WORKSPACE_STORAGE_KEY, wsId);
  } catch {
    // ignore storage errors
  }
  return wsId;
}

export async function checkHealth(timeoutMs: number = 8000): Promise<{
  status: string;
  service: string;
  vlm_enabled?: boolean;
  runtime_environment?: string;
  device?: string;
}> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch('/api/health', {
      signal: controller.signal,
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
      },
    });
    if (!res.ok) throw new Error(`Health check failed: HTTP ${res.status} ${res.statusText}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchScenes(customWsId?: string): Promise<SceneData> {
  const wsId = customWsId || getOrCreateWorkspaceId();
  const res = await fetch(`/api/scenes?workspace_id=${encodeURIComponent(wsId)}`, {
    headers: {
      'X-Workspace-ID': wsId,
    },
  });
  if (!res.ok) throw new Error(`Failed to fetch scenes: ${res.statusText}`);
  const json = await res.json();
  return json.data;
}

export async function fetchExamples(): Promise<ExampleQuery[]> {
  const res = await fetch('/api/examples');
  if (!res.ok) throw new Error(`Failed to fetch examples: ${res.statusText}`);
  const json = await res.json();
  return json.examples;
}

export async function processQuery(
  queryOrPayload: string | QueryPayload,
  customWsId?: string
): Promise<QueryResult> {
  const wsId = customWsId || getOrCreateWorkspaceId();
  const basePayload = typeof queryOrPayload === 'string' ? { query: queryOrPayload } : queryOrPayload;
  const payload: QueryPayload = {
    ...basePayload,
    workspace_id: basePayload.workspace_id || wsId,
  };

  const res = await fetch('/api/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Workspace-ID': wsId,
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || errorBody.error || `Server error (${res.status})`);
  }

  return res.json();
}

export async function uploadImage(file: File, customWsId?: string): Promise<UploadResponse> {
  const wsId = customWsId || getOrCreateWorkspaceId();
  const formData = new FormData();
  formData.append('file', file);
  formData.append('workspace_id', wsId);

  const res = await fetch('/api/images/upload', {
    method: 'POST',
    headers: {
      'X-Workspace-ID': wsId,
    },
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Upload error (${res.status})`);
  }

  return res.json();
}

export async function deleteScene(sceneId: string, customWsId?: string): Promise<DeleteSceneResponse> {
  const wsId = customWsId || getOrCreateWorkspaceId();
  const res = await fetch(`/api/scenes/${encodeURIComponent(sceneId)}?workspace_id=${encodeURIComponent(wsId)}`, {
    method: 'DELETE',
    headers: {
      'X-Workspace-ID': wsId,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || errorBody.error || `Failed to delete scene (${res.status})`);
  }

  return res.json();
}

export async function clearWorkspace(customWsId?: string): Promise<{ success: boolean; deleted_count?: number }> {
  const wsId = customWsId || getOrCreateWorkspaceId();
  const res = await fetch(`/api/workspace/clear?workspace_id=${encodeURIComponent(wsId)}`, {
    method: 'POST',
    headers: {
      'X-Workspace-ID': wsId,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || errorBody.error || `Failed to clear workspace (${res.status})`);
  }

  return res.json();
}

export async function fetchWorkspaceInfo(customWsId?: string): Promise<WorkspaceInfo> {
  const wsId = customWsId || getOrCreateWorkspaceId();
  const res = await fetch(`/api/workspace/info?workspace_id=${encodeURIComponent(wsId)}`, {
    headers: {
      'X-Workspace-ID': wsId,
    },
  });

  if (!res.ok) throw new Error(`Failed to fetch workspace info: ${res.statusText}`);
  const json = await res.json();
  return json.data;
}

export async function downloadAnalysisReport(result: QueryResult): Promise<string> {
  const res = await fetch('/api/report/generate-pdf', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(result),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error || `Failed to generate report (${res.status})`);
  }

  let filename = 'SatQuery_Research_Analysis_Report.pdf';
  const disposition = res.headers.get('Content-Disposition');
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename=["']?([^"';]+)["']?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 1500);

  return filename;
}

export async function downloadEvidenceZip(result: QueryResult): Promise<string> {
  const res = await fetch('/api/report/download-evidence-zip', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(result),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error || `Failed to download evidence package (${res.status})`);
  }

  let filename = 'SatQuery_Evidence_Package.zip';
  const disposition = res.headers.get('Content-Disposition');
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename=["']?([^"';]+)["']?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 1500);

  return filename;
}

/**
 * Single reliable API / Base URL mechanism for scientific evidence assets.
 * Seamlessly handles localhost:5173 (dev server proxy or direct port 8000),
 * localhost:8000 (direct production/FastAPI), or custom VITE_API_BASE_URL.
 */
export const BACKEND_URL = (
  (import.meta as any).env?.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && window.location.port === '5173'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : '')
).replace(/\/+$/, '');

export function resolveArtifactUrl(url?: string | null): string {
  if (!url) return '';
  let clean = url.trim().replace(/\\/g, '/');
  if (clean.startsWith('http://') || clean.startsWith('https://')) {
    return clean;
  }
  if (!clean.startsWith('/')) {
    clean = '/' + clean;
  }
  if (BACKEND_URL) {
    return `${BACKEND_URL}${clean}`;
  }
  return clean;
}

