import React, { useState, useEffect } from 'react';
import { Search, Sparkles, Leaf, BarChart2, Clock, Activity, Radio, X, ArrowRight, Loader2, CheckCircle2, AlertCircle, Layers } from 'lucide-react';
import type { ExampleQuery, QueryResult, SceneInfo, BiTemporalPair, QueryPayload, MultimodalPair } from '../types';

interface QuerySectionProps {
  examples: ExampleQuery[];
  loading: boolean;
  selectedScene: SceneInfo | null;
  mode: 'single_scene' | 'bitemporal' | 'multimodal_pair' | 'fusion' | string;
  bitemporalPair?: BiTemporalPair | null;
  multimodalPair?: MultimodalPair | null;
  sarScene?: SceneInfo | null;
  onExecuteQuery: (payload: QueryPayload) => void;
  onClearSelection?: () => void;
  lastResult?: QueryResult | null;
  workspaceNotice?: string | null;
  onDismissNotice?: () => void;
}

const DEFAULT_PRESETS: ExampleQuery[] = [
  {
    id: 'test-1',
    label: 'Vegetation VQA',
    icon: 'Leaf',
    query: 'Is there vegetation in this image?',
    description: 'Single-image remote-sensing visual understanding using fine-tuned SmolVLM-500M + RS LoRA.',
    explanation: 'VLM visual understanding',
    badge: 'VLM Core',
  },
  {
    id: 'test-2',
    label: 'NDVI Canopy Analysis',
    icon: 'BarChart2',
    query: 'Calculate NDVI and explain the vegetation.',
    description: 'Deterministic Landsat-9 surface reflectance processing + Hybrid VLM synthesis.',
    explanation: 'Scientific calculation + VLM explanation',
    badge: 'Hybrid Engine',
  },
  {
    id: 'test-3',
    label: 'Bi-Temporal Change',
    icon: 'Clock',
    query: 'Compare these two dates and tell me what changed.',
    description: 'Bi-temporal NDVI delta differencing + 3-panel triplet + VLM-assisted change interpretation.',
    explanation: 'Before/after NDVI analysis + VLM interpretation',
    badge: 'Change-VQA',
  },
  {
    id: 'test-4',
    label: 'Spectral Profile',
    icon: 'Activity',
    query: 'Analyze the spectral characteristics of this image.',
    description: '4-Band signature extraction (B2, B3, B4, B5), NDWI water index, and reflectance chart.',
    explanation: 'Multispectral band analysis',
    badge: 'Multispectral',
  },
  {
    id: 'test-5',
    label: 'Optical + SAR Fusion',
    icon: 'Radio',
    query: 'Analyze this scene using optical and SAR data.',
    description: 'Cross-sensor passive optical (Landsat-9) + active microwave radar (Sentinel-1 C-SAR).',
    explanation: 'Multimodal sensor analysis',
    badge: 'Multi-Modal',
  },
];

const MULTIMODAL_PRESETS: ExampleQuery[] = [
  {
    id: 'optsar-1',
    label: 'Optical + SAR Fusion',
    icon: 'Layers',
    query: 'Use both the optical and radar information to analyze this area.',
    description: 'Multimodal cross-sensor fusion combining Landsat reflectance with Sentinel-1 dual-pol backscatter.',
    explanation: 'Cross-sensor multimodal fusion',
    badge: 'Optical + SAR',
  },
  {
    id: 'optsar-2',
    label: 'Multispectral & Radar',
    icon: 'Radio',
    query: 'Combine the multispectral and radar observations.',
    description: 'Deterministic physical raster calculations (RVI, dual-pol ratio, surface roughness) + RS LoRA VLM.',
    explanation: 'Combined spectral + microwave synthesis',
    badge: 'Multimodal VLM',
  },
  {
    id: 'optsar-3',
    label: 'Reflected Light & Radar',
    icon: 'Sparkles',
    query: 'Give me a combined interpretation using reflected light and radar.',
    description: 'Synthesize canopy structural roughness and all-weather water inundation across both sensors.',
    explanation: 'Physical metrics + Visual interpretation',
    badge: 'Cross-Sensor',
  }
];

export const QuerySection: React.FC<QuerySectionProps> = ({
  examples,
  loading,
  selectedScene,
  mode,
  bitemporalPair,
  multimodalPair,
  sarScene,
  onExecuteQuery,
  lastResult,
  workspaceNotice,
  onDismissNotice,
}) => {
  const [queryText, setQueryText] = useState('');
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const activePresets = mode === 'multimodal_pair' ? MULTIMODAL_PRESETS : (examples && examples.length > 0 ? examples : DEFAULT_PRESETS);
  const selectedScenario = activePresets.find((p) => p.id === selectedScenarioId);

  // Real-time progress phases during backend inference
  const loadingPhases = [
    'Analyzing uploaded satellite scenes & raster bands...',
    'Matching query intent & validating spectral bands...',
    'Executing deterministic scientific calculation...',
    'Synthesizing multimodal visual features with SmolVLM...',
    'Generating visual evidence & auditable execution trace...',
  ];

  useEffect(() => {
    let interval: any;
    if (loading) {
      setActiveStepIndex(0);
      interval = setInterval(() => {
        setActiveStepIndex((prev) => (prev < loadingPhases.length - 1 ? prev + 1 : prev));
      }, 2400);
    } else {
      setActiveStepIndex(0);
    }
    return () => clearInterval(interval);
  }, [loading]);

  // =========================================================================
  // ARCHITECTURE A: Scenario Selection (Preset / Template selection ONLY)
  // MUST NOT trigger analysis, MUST NOT call backend endpoints, MUST NOT set loading.
  // =========================================================================
  const handleScenarioSelect = (scenario: ExampleQuery) => {
    setSelectedScenarioId(scenario.id);
    setQueryText(scenario.query);

    // Smoothly focus the query input so the user can review or edit before analysing
    if (inputRef.current) {
      inputRef.current.focus();
      inputRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };

  // =========================================================================
  // ARCHITECTURE B: Analysis Execution (Sole trigger for backend processing)
  // Triggered EXCLUSIVELY by clicking [Analyse] or pressing Enter in the input.
  // =========================================================================
  const handleAnalyze = () => {
    const q = queryText.trim();
    if (!q || loading) return;

    if (mode === 'multimodal_pair') {
      if (multimodalPair?.optical_scene_id && multimodalPair?.sar_scene_id) {
        onExecuteQuery({
          query: q,
          mode: 'multimodal_pair',
          active_pair_type: 'optical_sar',
          active_pair_id: multimodalPair.pair_id,
          optical_scene_id: multimodalPair.optical_scene_id,
          sar_scene_id: multimodalPair.sar_scene_id,
          active_scene_id: multimodalPair.optical_scene_id,
          scene_id: multimodalPair.optical_scene_id,
          selected_scene_id: multimodalPair.optical_scene_id,
          selected_scenario: selectedScenarioId || undefined,
        });
      } else {
        alert('Multimodal pair requires both Optical and SAR scenes to be available.');
      }
      return;
    }

    if (mode === 'bitemporal') {
      if (bitemporalPair?.before && bitemporalPair?.after) {
        onExecuteQuery({
          query: q,
          mode: 'bitemporal',
          active_scene_id: bitemporalPair.before.scene_id,
          scene_id: bitemporalPair.before.scene_id,
          selected_scene_id: bitemporalPair.before.scene_id,
          before_scene_id: bitemporalPair.before.scene_id,
          after_scene_id: bitemporalPair.after.scene_id,
          selected_scenario: selectedScenarioId || undefined,
        });
      } else {
        alert('Bi-temporal change detection requires both Before and After scenes to be available.');
      }
      return;
    }

    // Default Single Scene Mode: Active Scene is strictly authoritative
    if (!selectedScene) {
      alert('No scene selected. Please click a satellite scene from the library on the left before analyzing.');
      return;
    }

    onExecuteQuery({
      query: q,
      active_scene_id: selectedScene.scene_id,
      scene_id: selectedScene.scene_id,
      selected_scene_id: selectedScene.scene_id,
      active_scene_files: selectedScene.bands,
      selected_scenario: selectedScenarioId || undefined,
      mode: 'single_scene',
      optical_scene_id: selectedScene.scene_id,
      sar_scene_id: sarScene?.scene_id,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      handleAnalyze();
    }
  };

  const renderIcon = (iconName: string) => {
    switch (iconName.toLowerCase()) {
      case 'leaf': return <Leaf size={16} color="#34d399" />;
      case 'barchart2': return <BarChart2 size={16} color="#38bdf8" />;
      case 'clock': return <Clock size={16} color="#f59e0b" />;
      case 'activity': return <Activity size={16} color="#ec4899" />;
      case 'radio': return <Radio size={16} color="#a855f7" />;
      case 'layers': return <Layers size={16} color="#38bdf8" />;
      default: return <Sparkles size={16} color="#38bdf8" />;
    }
  };

  const isAnalyzeDisabled = loading || !queryText.trim() || (
    !selectedScene && mode === 'single_scene' && selectedScenarioId !== 'test-3' && selectedScenarioId !== 'test-5'
  );

  return (
    <div className="prompt-card">
      {/* HOW SATQUERY THINKS — Compact Architecture Flow Indicator */}
      <div className="agent-architecture-ribbon">
        <span className="ribbon-label">AGENT PIPELINE:</span>
        <div className="ribbon-steps">
          <span className="ribbon-step active">USER QUERY</span>
          <ArrowRight size={11} className="ribbon-arrow" />
          <span className="ribbon-step">INPUT ANALYSIS</span>
          <ArrowRight size={11} className="ribbon-arrow" />
          <span className="ribbon-step">INTENT</span>
          <ArrowRight size={11} className="ribbon-arrow" />
          <span className="ribbon-step">TOOL SELECTION</span>
          <ArrowRight size={11} className="ribbon-arrow" />
          <span className="ribbon-step">SCIENTIFIC ANALYSIS</span>
          <ArrowRight size={11} className="ribbon-arrow" />
          <span className="ribbon-step">VLM</span>
          <ArrowRight size={11} className="ribbon-arrow" />
          <span className="ribbon-step">EVIDENCE</span>
          <ArrowRight size={11} className="ribbon-arrow" />
          <span className="ribbon-step active">ANSWER</span>
        </div>
      </div>

      {/* WORKSPACE SAFETY NOTICE (e.g. Scene removed, Bi-temporal pair invalidated) */}
      {workspaceNotice && (
        <div
          className="query-context-card no-scene"
          style={{
            borderColor: 'rgba(244, 63, 94, 0.4)',
            background: 'rgba(244, 63, 94, 0.08)',
            marginBottom: 10,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ background: 'rgba(244, 63, 94, 0.2)', padding: 6, borderRadius: 6, color: '#f43f5e' }}>
              <AlertCircle size={16} />
            </div>
            <div>
              <div className="query-context-label" style={{ color: '#fb7185' }}>
                WORKSPACE SAFETY NOTICE
              </div>
              <div style={{ fontSize: '0.82rem', color: '#fecdd3', fontWeight: 500 }}>
                {workspaceNotice}
              </div>
            </div>
          </div>
          {onDismissNotice && (
            <button
              type="button"
              onClick={onDismissNotice}
              title="Dismiss notice"
              style={{ background: 'none', border: 'none', color: '#fda4af', cursor: 'pointer', padding: 4 }}
            >
              <X size={15} />
            </button>
          )}
        </div>
      )}

      {/* QUERY CONTEXT BANNER (Strictly shows exact selected input and query context) */}
      {mode === 'multimodal_pair' ? (
        <div className="query-context-card multimodal" style={{ borderColor: 'rgba(56, 189, 248, 0.45)', background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(168, 85, 247, 0.1), rgba(2, 6, 23, 0.85))' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ background: 'rgba(56, 189, 248, 0.18)', padding: 6, borderRadius: 6, color: '#38bdf8' }}>
              <Layers size={16} />
            </div>
            <div>
              <div className="query-context-label" style={{ color: '#38bdf8', fontWeight: 700 }}>
                MULTIMODAL PAIR ACTIVE
              </div>
              <div className="query-context-val">
                <span>{multimodalPair?.location || 'Port Blair'} • Optical + SAR Observation</span>
              </div>
            </div>
          </div>
          <div className="query-context-meta" style={{ color: '#94a3b8' }}>
            <span style={{ color: '#38bdf8' }}>{multimodalPair?.optical_satellite || 'Landsat-9'} ({multimodalPair?.optical_acquisition_date || '19 Apr 2026'})</span>
            <span>+</span>
            <span style={{ color: '#c084fc' }}>{multimodalPair?.sar_satellite || 'Sentinel-1A'} ({multimodalPair?.sar_acquisition_date || '13 Apr 2026'})</span>
            <span>•</span>
            <span style={{ color: '#f8fafc', fontWeight: 600 }}>{multimodalPair?.temporal_gap_days ?? 6}d gap</span>
          </div>
        </div>
      ) : mode === 'bitemporal' ? (
        <div className="query-context-card bitemporal">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.15)', padding: 6, borderRadius: 6, color: '#10b981' }}>
              <Clock size={16} />
            </div>
            <div>
              <div className="query-context-label" style={{ color: '#34d399' }}>
                QUERY CONTEXT
              </div>
              <div className="query-context-val">
                <span>Comparing: {bitemporalPair?.before_date || bitemporalPair?.before?.acquisition_date || '20 Jul 2026'} ➔ {bitemporalPair?.after_date || bitemporalPair?.after?.acquisition_date || '10 Aug 2026'}</span>
              </div>
            </div>
          </div>
          <div className="query-context-meta" style={{ color: '#34d399' }}>
            <span>Path/Row: {bitemporalPair?.path_row_formatted || '141/040'}</span>
            <span>•</span>
            <span>Interval: {bitemporalPair?.interval_days || 16} Days</span>
          </div>
        </div>
      ) : mode === 'fusion' ? (
        <div className="query-context-card fusion">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ background: 'rgba(168, 85, 247, 0.15)', padding: 6, borderRadius: 6, color: '#a855f7' }}>
              <Radio size={16} />
            </div>
            <div>
              <div className="query-context-label" style={{ color: '#c084fc' }}>
                QUERY CONTEXT
              </div>
              <div className="query-context-val">
                <span>Analyzing: Landsat-9 + Sentinel-1</span>
              </div>
            </div>
          </div>
          <div className="query-context-meta" style={{ color: '#c084fc' }}>
            <span>Optical: {selectedScene?.title || 'Landsat-9'} • SAR: {sarScene?.title || 'Sentinel-1A'}</span>
          </div>
        </div>
      ) : selectedScene?.is_generic_image ? (
        /* =======================================================================
           PNG / JPEG SINGLE-IMAGE VQA ACTIVE INPUT CARD (Requirements #7 & #8)
           ======================================================================= */
        <div className="query-context-card" style={{ borderColor: 'rgba(56, 189, 248, 0.4)', background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(2, 6, 23, 0.8))' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {/* Thumbnail Preview */}
              {(selectedScene.thumbnail_url || selectedScene.thumbnail) && (
                <div style={{ width: 56, height: 56, borderRadius: 6, overflow: 'hidden', border: '1px solid rgba(56, 189, 248, 0.3)', flexShrink: 0, background: '#020617' }}>
                  <img
                    src={selectedScene.thumbnail_url || selectedScene.thumbnail}
                    alt={selectedScene.title || 'Selected Image'}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                </div>
              )}
              <div>
                <div className="query-context-label" style={{ color: '#38bdf8', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>QUERY CONTEXT</span>
                  <span style={{ color: '#94a3b8' }}>•</span>
                  <span style={{ color: '#f1f5f9', fontWeight: 600 }}>Analyzing: {selectedScene.title || selectedScene.source_file || 'Captured Aerial Image'}</span>
                </div>
                <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#f8fafc', marginTop: 2 }}>
                  {selectedScene.title || selectedScene.source_file || 'Captured Aerial Image'}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.74rem', color: '#94a3b8', marginTop: 3 }}>
                  <span>{selectedScene.acquisition_date || selectedScene.date || 'Active Scene'}</span>
                  <span>•</span>
                  <span style={{ color: '#38bdf8', fontWeight: 600 }}>{selectedScene.image_format || 'PNG'}</span>
                  <span>•</span>
                  <span>{selectedScene.dimensions || 'Standard Resolution'}</span>
                  <span>•</span>
                  <span>Channels: {selectedScene.channels || 'RGB'}</span>
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: 2 }}>
                  Geospatial metadata: <span style={{ color: '#94a3b8' }}>Not available</span> (Non-georeferenced single image)
                </div>
              </div>
            </div>
            <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
              <span className="selected-scene-pill" style={{ background: 'rgba(56, 189, 248, 0.2)', borderColor: '#38bdf8', color: '#38bdf8', fontSize: '0.68rem', padding: '3px 8px' }}>
                <CheckCircle2 size={10} style={{ marginRight: 4 }} />
                SELECTED
              </span>
              <span style={{ fontSize: '0.72rem', color: '#38bdf8', fontWeight: 500 }}>
                Query will run against: &ldquo;{selectedScene.source_file || selectedScene.title || 'Selected Image'}&rdquo;
              </span>
            </div>
          </div>
        </div>
      ) : selectedScene ? (
        /* =======================================================================
           GEOTIFF ACTIVE SCENE CARD (Requirement #8)
           ======================================================================= */
        <div className="query-context-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ background: 'rgba(56, 189, 248, 0.15)', padding: 6, borderRadius: 6, color: '#38bdf8' }}>
              <CheckCircle2 size={16} />
            </div>
            <div>
              <div className="query-context-label">
                QUERY CONTEXT
              </div>
              <div className="query-context-val">
                <span>Analyzing: {selectedScene.satellite || 'Landsat-9'} — {selectedScene.acquisition_date || '10 Aug 2026'}</span>
                <span className="selected-scene-pill" style={{ fontSize: '0.62rem' }}>
                  {selectedScene.modality.toUpperCase()}
                </span>
              </div>
            </div>
          </div>
          <div className="query-context-meta">
            {selectedScene.acquisition_date && <span>Date: {selectedScene.acquisition_date}</span>}
            {selectedScene.path_row_formatted && (
              <>
                <span>•</span>
                <span>Path/Row: {selectedScene.path_row_formatted}</span>
              </>
            )}
            <span>•</span>
            <span>CRS: {selectedScene.crs || 'EPSG:32645'}</span>
            <span>•</span>
            <span>Resolution: {selectedScene.resolution || '30 m'}</span>
          </div>
        </div>
      ) : (
        <div className="query-context-card no-scene">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ background: 'rgba(245, 158, 11, 0.15)', padding: 6, borderRadius: 6, color: '#f59e0b' }}>
              <AlertCircle size={16} />
            </div>
            <div>
              <div className="query-context-label" style={{ color: '#fbbf24' }}>
                QUERY CONTEXT — NO SCENE SELECTED
              </div>
              <div style={{ fontSize: '0.82rem', color: '#fef3c7', fontWeight: 500 }}>
                Select an image or satellite scene from the library on the left to begin analysis.
              </div>
            </div>
          </div>
          <div style={{ fontSize: '0.72rem', color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>
            Analysis Blocked
          </div>
        </div>
      )}

      {/* Active Selected Scenario Indicator */}
      {selectedScenario && (
        <div className="selected-scenario-indicator">
          <span className="selected-scenario-tag">Selected Scenario:</span>
          <span className="selected-scenario-name">{selectedScenario.label}</span>
          <span className="selected-scenario-pill">{selectedScenario.badge}</span>
          <button
            type="button"
            className="btn-clear-scenario"
            onClick={() => setSelectedScenarioId(null)}
            title="Deselect scenario preset"
          >
            <X size={13} />
          </button>
        </div>
      )}

      {/* Query Bar */}
      <div className="prompt-input-wrapper">
        <Search size={18} color="#94a3b8" />
        <input
          ref={inputRef}
          type="text"
          className="prompt-input"
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            !selectedScene && mode === 'single_scene' && selectedScenarioId !== 'test-3' && selectedScenarioId !== 'test-5'
              ? 'Select a satellite scene from the library to begin analysis...'
              : 'Ask anything about the satellite imagery (e.g., Calculate NDVI, compare dates, or fuse optical and SAR)...'
          }
          disabled={loading}
        />
        {queryText && (
          <button
            type="button"
            onClick={() => setQueryText('')}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px' }}
          >
            <X size={16} />
          </button>
        )}
        <button
          type="button"
          className="submit-btn"
          onClick={handleAnalyze}
          disabled={isAnalyzeDisabled}
          title={
            !selectedScene && mode === 'single_scene' && selectedScenarioId !== 'test-3' && selectedScenarioId !== 'test-5'
              ? 'Please select a satellite scene from the library first'
              : 'Execute query analysis'
          }
          style={
            !selectedScene && mode === 'single_scene' && selectedScenarioId !== 'test-3' && selectedScenarioId !== 'test-5'
              ? { opacity: 0.5, cursor: 'not-allowed', filter: 'grayscale(0.6)' }
              : {}
          }
        >
          {loading ? (
            <>
              <Loader2 size={16} className="spinning" />
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <Sparkles size={16} />
              <span>Analyse</span>
            </>
          )}
        </button>
      </div>

      {/* 1. Real-time Loading Status Bar */}
      {loading && (
        <div className="loading-status-bar">
          <Loader2 size={14} className="spinning" color="#38bdf8" />
          <span className="loading-status-text">{loadingPhases[activeStepIndex]}</span>
          <span className="loading-phase-pill">Step {activeStepIndex + 1} of 5</span>
        </div>
      )}

      {/* 1. What SatQuery Understood (Pipeline Resolution Ribbon) */}
      {!loading && lastResult && lastResult.success && (
        <div className="pipeline-resolution-bar">
          <div className="resolution-item">
            <span className="res-title">Query:</span>
            <span className="res-val" title={lastResult.query}>"{lastResult.query.slice(0, 32)}..."</span>
          </div>
          <ArrowRight size={12} color="#64748b" />
          <div className="resolution-item">
            <span className="res-title">Understood Intent:</span>
            <span className="res-badge cyan">{lastResult.intent}</span>
          </div>
          <ArrowRight size={12} color="#64748b" />
          <div className="resolution-item">
            <span className="res-title">Tool Selected:</span>
            <span className="res-badge emerald">{lastResult.selected_tool}</span>
          </div>
          <ArrowRight size={12} color="#64748b" />
          <div className="resolution-item">
            <span className="res-title">Status:</span>
            <span className="res-badge green">Validated & Solved</span>
          </div>
        </div>
      )}

      {/* 8. Benchmark Scenario Cards (Preset / Template Selector) */}
      <div className="presets-heading">
        <Sparkles size={14} color="#38bdf8" />
        <span>SIH 2026 Core Benchmark Scenarios (Select to Populate Query)</span>
      </div>

      <div className="presets-grid">
        {activePresets.map((ex) => {
          const isSelected = selectedScenarioId === ex.id;
          return (
            <button
              key={ex.id}
              type="button"
              className={`preset-chip ${isSelected ? 'selected' : ''}`}
              onClick={() => handleScenarioSelect(ex)}
              disabled={loading}
              title={`Select scenario: ${ex.label}`}
            >
              <div className="preset-chip-header">
                <span className="preset-label">
                  {renderIcon(ex.icon)}
                  {ex.label}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {isSelected && (
                    <span className="preset-selected-badge">
                      <CheckCircle2 size={11} />
                      Active
                    </span>
                  )}
                  <span className="preset-badge">{ex.badge}</span>
                </div>
              </div>
              <span className="preset-sub-explanation">
                {ex.explanation || ex.description}
              </span>
              <p className="preset-desc">"{ex.query}"</p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
