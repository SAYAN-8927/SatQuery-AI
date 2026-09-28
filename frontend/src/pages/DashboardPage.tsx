import React, { useEffect, useState } from 'react';
import confetti from 'canvas-confetti';
import { Header } from '../components/Header';
import { SceneSidebar } from '../components/SceneSidebar';
import { QuerySection } from '../components/QuerySection';
import { ResultView } from '../components/ResultView';
import { EvidenceViewer } from '../components/EvidenceViewer';
import { MetricsGrid } from '../components/MetricsGrid';
import { ConfidenceCard } from '../components/ConfidenceCard';
import { ExecutionTrace } from '../components/ExecutionTrace';
import { checkHealth, fetchScenes, fetchExamples, processQuery, deleteScene, clearWorkspace } from '../api';
import type { SceneData, ExampleQuery, QueryResult, UploadResponse, QueryPayload, SceneInfo } from '../types';
import { Shield, Terminal, Trash2, AlertTriangle } from 'lucide-react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: any;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: any) {
    return { hasError: true, error };
  }

  componentDidCatch(error: any, errorInfo: any) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="interpretation-card" style={{ borderColor: '#f43f5e', background: 'rgba(244,63,94,0.08)', padding: 24 }}>
          <h3 style={{ color: '#fb7185', fontSize: '1rem', fontWeight: 600 }}>Display Rendering Notice</h3>
          <p style={{ color: '#fda4af', fontSize: '0.85rem', marginTop: 8 }}>
            {String(this.state.error?.message || this.state.error)}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="submit-btn"
            style={{ width: 'fit-content', marginTop: 14, padding: '6px 14px', fontSize: '0.8rem' }}
          >
            Reset View
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

interface DashboardPageProps {
  onGoHome?: () => void;
  onSelectBand?: (sceneId: string, band: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onGoHome, onSelectBand }) => {
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [vlmEnabled, setVlmEnabled] = useState<boolean | undefined>(() => {
    if (typeof window !== 'undefined' && (window.location.hostname.includes('render.com') || window.location.hostname.includes('onrender.com'))) {
      return false;
    }
    return undefined;
  });
  const [sceneData, setSceneData] = useState<SceneData | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [queryMode, setQueryMode] = useState<'single_scene' | 'bitemporal' | 'multimodal_pair' | 'fusion'>('single_scene');
  const [examples, setExamples] = useState<ExampleQuery[]>([]);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [sidebarLoading, setSidebarLoading] = useState<boolean>(false);

  // Deletion & Workspace Safety State
  const [sceneToDelete, setSceneToDelete] = useState<SceneInfo | null>(null);
  const [showClearModal, setShowClearModal] = useState<boolean>(false);
  const [deleteLoading, setDeleteLoading] = useState<boolean>(false);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);

  // Initial Data Loading
  const loadInitialData = async (): Promise<SceneData | null> => {
    try {
      setSidebarLoading(true);

      try {
        const health = await checkHealth();
        setBackendOnline(health.status === 'ok');
        if (health.vlm_enabled !== undefined) {
          setVlmEnabled(health.vlm_enabled);
        }
      } catch (hErr) {
        console.warn('Health check issue:', hErr);
        setBackendOnline(false);
      }

      let loadedScenes: SceneData | null = null;
      try {
        loadedScenes = await fetchScenes();
        if (loadedScenes) {
          setSceneData(loadedScenes);
        }
      } catch (sErr) {
        console.error('Failed to fetch scenes:', sErr);
      }

      try {
        const ex = await fetchExamples();
        if (ex && ex.length > 0) {
          setExamples(ex);
        }
      } catch (exErr) {
        console.warn('Failed to fetch examples, using defaults:', exErr);
      }

      return loadedScenes;
    } catch (err) {
      console.error('Initial loading error:', err);
      return null;
    } finally {
      setSidebarLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const selectedScene = sceneData?.scenes?.find((s) => s.scene_id === selectedSceneId) || null;
  const bitemporalPair = sceneData?.bi_temporal_pairs && sceneData.bi_temporal_pairs.length > 0 ? sceneData.bi_temporal_pairs[0] : null;
  const multimodalPair = sceneData?.multimodal_pairs && sceneData.multimodal_pairs.length > 0 ? sceneData.multimodal_pairs[0] : null;
  const sarScene = sceneData?.scenes?.find((s) => s.modality === 'sar' || s.scene_id.startsWith('S1')) || null;

  const handleSelectScene = (sceneId: string) => {
    setSelectedSceneId(sceneId);
    setResult(null); // Clear previous result immediately so stale results cannot linger
    setQueryMode('single_scene');
    setWorkspaceNotice(null);
  };

  const handleSelectBiTemporal = (_pair: any) => {
    setSelectedSceneId(null);
    setQueryMode('bitemporal');
    setResult(null); // Clear previous single-scene result
    setWorkspaceNotice(null);
  };

  const handleSelectMultimodal = (_pair: any) => {
    setSelectedSceneId(null);
    setQueryMode('multimodal_pair');
    setResult(null); // Clear previous result immediately
    setWorkspaceNotice(null);
  };

  // Scene Deletion Handlers
  const handleRequestDeleteScene = (scene: SceneInfo) => {
    setSceneToDelete(scene);
  };

  const handleConfirmDeleteScene = async () => {
    if (!sceneToDelete) return;
    const deletedId = sceneToDelete.scene_id;
    try {
      setDeleteLoading(true);
      await deleteScene(deletedId);

      // SAFETY 1: Single Scene - If deleted scene was selected context, clear it immediately
      if (selectedSceneId === deletedId) {
        setSelectedSceneId(null);
        setResult(null); // Clear result immediately so deleted scene analysis cannot be displayed
        setWorkspaceNotice('Scene removed. Select another scene to continue analysis.');
      }

      // SAFETY 2: Bi-Temporal - If deleted scene was in bi-temporal pair, invalidate
      if (
        bitemporalPair &&
        (bitemporalPair.before?.scene_id === deletedId || bitemporalPair.after?.scene_id === deletedId)
      ) {
        if (queryMode === 'bitemporal') {
          setQueryMode('single_scene');
          setWorkspaceNotice('Bi-temporal pair unavailable. One of the selected scenes was removed.');
        }
      }

      // SAFETY 3: Multimodal Optical + SAR - If deleted scene was in multimodal pair, invalidate
      if (
        multimodalPair &&
        (multimodalPair.optical_scene_id === deletedId || multimodalPair.sar_scene_id === deletedId)
      ) {
        if (queryMode === 'multimodal_pair' || queryMode === 'fusion') {
          setQueryMode('single_scene');
          setWorkspaceNotice('Multimodal pair unavailable. One of the selected scenes was removed.');
        }
      }

      // SAFETY 4: General Fusion - If deleted scene was in fusion context
      if (queryMode === 'fusion') {
        if (selectedSceneId === deletedId || sarScene?.scene_id === deletedId) {
          setWorkspaceNotice('Optical or SAR input removed. Select another compatible input.');
        }
      }

      setSceneToDelete(null);
      await loadInitialData();
    } catch (err: any) {
      alert(`Failed to delete scene: ${err.message}`);
    } finally {
      setDeleteLoading(false);
    }
  };

  // Clear Workspace Handlers
  const handleConfirmClearWorkspace = async () => {
    try {
      setDeleteLoading(true);
      await clearWorkspace();
      setSelectedSceneId(null);
      setQueryMode('single_scene');
      setResult(null);
      setWorkspaceNotice('Workspace cleared. Upload satellite scenes to begin analysis.');
      setShowClearModal(false);
      await loadInitialData();
    } catch (err: any) {
      alert(`Clear workspace failed: ${err.message}`);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleExecuteQuery = async (queryPayload: QueryPayload | string) => {
    const payload: QueryPayload = typeof queryPayload === 'string'
      ? {
          query: queryPayload,
          active_scene_id: selectedSceneId || undefined,
          scene_id: selectedSceneId || undefined,
          mode: queryMode
        }
      : {
          ...queryPayload,
          active_scene_id: queryPayload.active_scene_id || selectedSceneId || undefined,
          scene_id: queryPayload.scene_id || selectedSceneId || undefined,
        };

    try {
      setLoading(true);
      const res = await processQuery(payload);
      setResult(res);

      if (res && res.success) {
        try {
          confetti({
            particleCount: 40,
            spread: 60,
            origin: { y: 0.85 },
            colors: ['#38bdf8', '#10b981', '#a855f7'],
          });
        } catch {
          // ignore confetti errors
        }
      }
    } catch (err: any) {
      setResult({
        success: false,
        query: payload.query,
        intent: 'error',
        selected_tool: 'none',
        error: err.message || 'Failed to process query',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleUploadSuccess = async (res: UploadResponse) => {
    setWorkspaceNotice(null);
    try {
      const data = await loadInitialData();
      if (data && data.scenes && data.scenes.length > 0) {
        // Auto-select the newly uploaded image!
        const targetSceneId = res.scene_id || (res.filename ? res.filename.replace(/\.[^/.]+$/, '') : null);
        if (targetSceneId) {
          const matched = data.scenes.find(
            (s) => s.scene_id === targetSceneId ||
                   s.source_file === res.filename ||
                   s.scene_id.toLowerCase() === targetSceneId.toLowerCase() ||
                   s.scene_id.toLowerCase().includes(targetSceneId.toLowerCase())
          );
          if (matched) {
            setSelectedSceneId(matched.scene_id);
            setQueryMode('single_scene');
            setResult(null);
          } else {
            const firstGeneric = data.scenes.find(s => s.is_generic_image);
            if (firstGeneric) {
              setSelectedSceneId(firstGeneric.scene_id);
              setQueryMode('single_scene');
              setResult(null);
            }
          }
        }
      }
    } catch (err) {
      console.error('Error handling upload success:', err);
    }
  };

  return (
    <div className="app-container">
      <Header backendOnline={backendOnline} onGoHome={onGoHome} vlmEnabled={vlmEnabled} />

      <div className="main-layout">
        <SceneSidebar
          sceneData={sceneData}
          loading={sidebarLoading}
          selectedSceneId={selectedSceneId}
          onRefresh={loadInitialData}
          onUploadSuccess={handleUploadSuccess}
          onSelectBand={(sceneId, band) => onSelectBand?.(sceneId, band)}
          onSelectScene={handleSelectScene}
          onSelectBiTemporal={handleSelectBiTemporal}
          isBiTemporalActive={queryMode === 'bitemporal'}
          multimodalPair={multimodalPair}
          onSelectMultimodal={handleSelectMultimodal}
          isMultimodalActive={queryMode === 'multimodal_pair'}
          onRequestDeleteScene={handleRequestDeleteScene}
          onRequestClearWorkspace={() => setShowClearModal(true)}
        />

        <main className="stage-content">
          {/* Query Bar & 1-Click SIH Benchmark Presets */}
          <QuerySection
            examples={examples}
            loading={loading}
            selectedScene={selectedScene}
            mode={queryMode}
            bitemporalPair={bitemporalPair}
            multimodalPair={multimodalPair}
            sarScene={sarScene}
            onExecuteQuery={handleExecuteQuery}
            lastResult={result}
            workspaceNotice={workspaceNotice}
            onDismissNotice={() => setWorkspaceNotice(null)}
          />

          {/* Result Main Stage with Error Boundary */}
          <ErrorBoundary>
            <div className="results-grid">
              {/* Primary Analysis & Visual Evidence Column */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                <ResultView result={result} loading={loading} />

                <EvidenceViewer
                  evidence={result?.analysis?.evidence}
                  selectedTool={result?.selected_tool}
                />

                <MetricsGrid result={result} />

                <ExecutionTrace trace={result?.execution_trace} />
              </div>

              {/* Scientific Confidence & System Sidebar Column */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <ConfidenceCard
                  confidence={result?.interpretation?.confidence}
                  deploymentConstrained={Boolean(
                    result?.analysis?.deployment_constrained ||
                    (result as any)?.deployment_constrained ||
                    (result?.interpretation?.confidence as any)?.deployment_constrained ||
                    (vlmEnabled === false)
                  )}
                />

                {/* Hackathon Specs Card */}
                <div className="prompt-card" style={{ padding: 18, fontSize: '0.8rem', color: '#94a3b8' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#38bdf8', fontWeight: 600, marginBottom: 8 }}>
                    <Shield size={16} />
                    <span>SIH Scientific Pipeline</span>
                  </div>
                  <p style={{ lineHeight: 1.5, marginBottom: 10 }}>
                    Hybrid architecture pairing physical raster calculations with SmolVLM-500M vision synthesis.
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Optical Engine:</span>
                      <span style={{ color: '#f8fafc' }}>Landsat-9 OLI-2</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Radar Engine:</span>
                      <span style={{ color: '#f8fafc' }}>Sentinel-1 C-SAR</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>VLM Weights:</span>
                      <span style={{ color: '#f8fafc' }}>RS LoRA FP16</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Confidence:</span>
                      <span style={{ color: '#10b981' }}>Estimated (Audited)</span>
                    </div>
                  </div>
                </div>

                {/* Quick Terminal Guide */}
                <div className="prompt-card" style={{ padding: 18, fontSize: '0.75rem', color: '#64748b' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#a855f7', fontWeight: 600, marginBottom: 8 }}>
                    <Terminal size={14} />
                    <span>Multimodal Sensor Keys</span>
                  </div>
                  <p style={{ lineHeight: 1.4 }}>
                    • <strong>B4 + B5</strong>: NDVI Vegetation Canopy<br />
                    • <strong>B3 + B5</strong>: NDWI Water Bodies<br />
                    • <strong>VV + VH</strong>: SAR Surface & Canopy Scattering<br />
                    • <strong>ΔNDVI</strong>: Bi-temporal Greening/Loss
                  </p>
                </div>
              </div>
            </div>
          </ErrorBoundary>
        </main>
      </div>

      {/* 3. Delete Scene Confirmation Modal */}
      {sceneToDelete && (
        <div className="satquery-modal-backdrop" onClick={() => !deleteLoading && setSceneToDelete(null)}>
          <div className="satquery-confirmation-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-danger">
              <div className="modal-icon-badge">
                <Trash2 size={18} />
              </div>
              <div className="modal-title-danger">Delete this scene?</div>
            </div>

            <div className="modal-body-meta">
              <div className="modal-scene-name">
                {sceneToDelete.satellite || 'Satellite Scene'} {sceneToDelete.sensor ? `• ${sceneToDelete.sensor.split(' ')[0]}` : ''}
              </div>
              <div className="modal-scene-details">
                {sceneToDelete.acquisition_date || sceneToDelete.date || 'Active Scene'} • {sceneToDelete.bands?.length || 0} bands ({sceneToDelete.bands?.join(', ') || ''})
              </div>
            </div>

            <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.5, margin: '8px 0 0 0' }}>
              This will remove the uploaded scene and its generated previews.
            </p>

            <div className="modal-actions-row">
              <button
                type="button"
                className="btn-modal-cancel"
                onClick={() => setSceneToDelete(null)}
                disabled={deleteLoading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-modal-danger"
                onClick={handleConfirmDeleteScene}
                disabled={deleteLoading}
              >
                {deleteLoading ? 'Deleting...' : 'Delete Scene'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Clear Workspace Confirmation Modal */}
      {showClearModal && (
        <div className="satquery-modal-backdrop" onClick={() => !deleteLoading && setShowClearModal(false)}>
          <div className="satquery-confirmation-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-danger">
              <div className="modal-icon-badge">
                <AlertTriangle size={18} />
              </div>
              <div className="modal-title-danger">Clear Workspace?</div>
            </div>

            <p style={{ fontSize: '0.84rem', color: '#cbd5e1', lineHeight: 1.5, margin: '12px 0 8px 0' }}>
              This will remove all uploaded satellite datasets from the current workspace.
            </p>

            <div className="modal-actions-row">
              <button
                type="button"
                className="btn-modal-cancel"
                onClick={() => setShowClearModal(false)}
                disabled={deleteLoading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-modal-danger"
                onClick={handleConfirmClearWorkspace}
                disabled={deleteLoading}
              >
                {deleteLoading ? 'Clearing...' : 'Clear Workspace'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
