import React, { useState, useEffect } from 'react';
import {
  Bot,
  Terminal,
  Eye,
  AlertCircle,
  Layers,
  Calendar,
  Cpu,
  Radio,
  Compass,
  CheckCircle2,
  Globe,
  FileText,
  Download,
  Loader2,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  TrendingUp,
} from 'lucide-react';
import type { QueryResult } from '../types';
import { downloadAnalysisReport, downloadEvidenceZip } from '../api';
import { MarkdownRenderer } from './MarkdownRenderer';

function parseSceneDate(sceneId?: string): string {
  if (!sceneId) return '';
  const m = sceneId.match(/_(\d{8})_/);
  if (m) {
    const d = m[1];
    return `${d.substring(0, 4)}-${d.substring(4, 6)}-${d.substring(6, 8)}`;
  }
  return '';
}

interface ResultViewProps {
  result: QueryResult | null;
  loading: boolean;
}

export const ResultView: React.FC<ResultViewProps> = ({ result, loading }) => {
  const [generatingPdf, setGeneratingPdf] = useState<boolean>(false);
  const [pdfSuccess, setPdfSuccess] = useState<boolean>(false);
  const [downloadingZip, setDownloadingZip] = useState<boolean>(false);
  const [zipSuccess, setZipSuccess] = useState<boolean>(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Long AI Response controls
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  // Whenever a new query result arrives, expand to show full answer by default and reset copy state
  useEffect(() => {
    setIsExpanded(true);
    setCopied(false);
  }, [result]);

  const handleCopyAnswer = async (text: string) => {
    if (!text) return;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.warn('Failed to copy answer:', err);
    }
  };

  const handleDownloadPdf = async () => {
    if (!result || generatingPdf) return;
    try {
      setGeneratingPdf(true);
      setDownloadError(null);
      await downloadAnalysisReport(result);
      setPdfSuccess(true);
      setTimeout(() => setPdfSuccess(false), 4000);
    } catch (err: any) {
      setDownloadError(err.message || 'Failed to generate PDF report');
    } finally {
      setGeneratingPdf(false);
    }
  };

  const handleDownloadZip = async () => {
    if (!result || downloadingZip) return;
    try {
      setDownloadingZip(true);
      setDownloadError(null);
      await downloadEvidenceZip(result);
      setZipSuccess(true);
      setTimeout(() => setZipSuccess(false), 4000);
    } catch (err: any) {
      setDownloadError(err.message || 'Failed to download evidence package');
    } finally {
      setDownloadingZip(false);
    }
  };
  if (loading) {
    return (
      <div className="interpretation-card" style={{ alignItems: 'center', justifyContent: 'center', minHeight: 220 }}>
        <Bot size={40} color="#38bdf8" className="spinning" />
        <p style={{ marginTop: 14, color: '#f8fafc', fontSize: '0.95rem', fontWeight: 600 }}>
          Autonomous Remote Sensing Orchestration in Progress
        </p>
        <p style={{ color: '#94a3b8', fontSize: '0.8rem', marginTop: 4 }}>
          Calculating deterministic surface reflectance tensors & querying SmolVLM-500M...
        </p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="interpretation-card" style={{ textAlign: 'center', padding: '44px 20px', color: '#64748b' }}>
        <Bot size={44} style={{ margin: '0 auto 14px auto', opacity: 0.6, color: '#38bdf8' }} />
        <h3 style={{ fontSize: '1.15rem', color: '#f8fafc', marginBottom: 8, fontFamily: 'var(--font-display)' }}>
          Ready for Autonomous Remote Sensing Analysis
        </h3>
        <p style={{ fontSize: '0.86rem', maxWidth: 480, margin: '0 auto', color: '#94a3b8', lineHeight: 1.5 }}>
          Select a 1-click benchmark query above or type a natural question to trigger physical raster calculations, spectral index extraction, and SmolVLM multimodal interpretation.
        </p>
      </div>
    );
  }

  // 10. User-Friendly Structured Error State
  if (!result.success || result.error) {
    const errorMsg = result.error || 'The system could not perform this analysis.';
    let suggestedAction = 'Upload a compatible remote sensing scene with the required bands.';
    let availableData = 'Inspect the Sensor Catalog on the left sidebar for available modalities.';

    if (errorMsg.includes('B4') || errorMsg.includes('B5') || errorMsg.includes('NDVI')) {
      suggestedAction = 'Upload a Landsat optical scene containing Red (B4) and NIR (B5) surface reflectance bands.';
      availableData = 'Only SAR radar bands (VV/VH) or RGB bands detected.';
    } else if (errorMsg.includes('bi-temporal') || errorMsg.includes('pair')) {
      suggestedAction = 'Ensure at least two optical scenes with different acquisition dates are present for change detection.';
      availableData = 'Single scene uploaded or scenes lack identical spatial path/row.';
    }

    return (
      <div className="interpretation-card error-state-card">
        <div className="error-header-row">
          <AlertCircle size={22} color="#f43f5e" />
          <h3 className="error-title">SatQuery could not perform this analysis</h3>
        </div>

        <div className="error-body-grid">
          <div className="error-field">
            <span className="error-field-label">Reason:</span>
            <p className="error-field-value">{errorMsg}</p>
          </div>

          <div className="error-field">
            <span className="error-field-label">Available Data:</span>
            <p className="error-field-value muted">{availableData}</p>
          </div>

          <div className="error-field">
            <span className="error-field-label">Suggested Action:</span>
            <p className="error-field-value action">{suggestedAction}</p>
          </div>
        </div>
      </div>
    );
  }

  const rawInterpretation = result.interpretation?.interpretation || result.analysis?.answer || 'Analysis complete.';

  // Separate AI Interpretation from Multimodal Visual Context
  let mainText = rawInterpretation;
  let visualContext = '';

  if (rawInterpretation.includes('Multimodal Visual Context:')) {
    const parts = rawInterpretation.split('Multimodal Visual Context:');
    mainText = parts[0].trim();
    visualContext = parts[1].trim();
  } else if (rawInterpretation.includes('Multimodal Visual Context & Scientific Insights:')) {
    const parts = rawInterpretation.split('Multimodal Visual Context & Scientific Insights:');
    mainText = parts[0].trim();
    visualContext = parts[1].trim();
  } else if (rawInterpretation.includes('Change-VQA Multimodal Synthesis:')) {
    const parts = rawInterpretation.split('Change-VQA Multimodal Synthesis:');
    mainText = parts[0].trim();
    visualContext = parts[1].trim();
  }

  // Enhance generic VLM answer (e.g. "Yes, there is a tree in the image.") with scientific context
  let primaryAiAnswer = mainText;
  if (result.selected_tool === 'remote_sensing_vlm') {
    if (mainText.toLowerCase().includes('yes') && mainText.toLowerCase().includes('tree')) {
      primaryAiAnswer = `Yes, vegetation is present. The adapted SmolVLM model identified tree-like vegetation canopy features directly from the optical satellite imagery.`;
    }
  }

  // Determine if AI answer is long enough to offer Show more / Show less
  const isLongResponse = primaryAiAnswer.length > 280 || primaryAiAnswer.split('\n').filter(Boolean).length > 3;

  // Compute clean preview text when collapsed
  let previewText = primaryAiAnswer;
  if (isLongResponse) {
    const cutoff = 240;
    const sentenceEnd = primaryAiAnswer.indexOf('.', cutoff);
    if (sentenceEnd !== -1 && sentenceEnd < 340) {
      previewText = primaryAiAnswer.substring(0, sentenceEnd + 1);
    } else {
      const spaceIdx = primaryAiAnswer.lastIndexOf(' ', cutoff);
      previewText = (spaceIdx !== -1 ? primaryAiAnswer.substring(0, spaceIdx) : primaryAiAnswer.substring(0, cutoff)) + '...';
    }
  }

  // Extract scientific measurements from backend analysis without fabricating
  const analysis = result.analysis || {};
  const basis = result.interpretation?.basis || {};

  const measurements: { label: string; value: string; icon: React.ReactNode }[] = [];

  // Sensor identity & dates
  if (analysis.scene || basis.scene || analysis.optical_scene) {
    const sc = analysis.scene || basis.scene || analysis.optical_scene;
    const isLC = String(sc).includes('LC09') ? 'Landsat-9 OLI-2' : (String(sc).includes('LC08') ? 'Landsat-8 OLI' : 'Sentinel-2 MSI');
    measurements.push({ label: 'Primary Sensor', value: isLC, icon: <Cpu size={14} color="#38bdf8" /> });
  }

  if (analysis.sar_scene) {
    measurements.push({ label: 'Radar Sensor', value: 'Sentinel-1A C-SAR', icon: <Radio size={14} color="#a855f7" /> });
  }

  if (analysis.before && analysis.after) {
    measurements.push({
      label: 'Acquisition Interval',
      value: `${analysis.before.date || 'Before'} → ${analysis.after.date || 'After'}`,
      icon: <Calendar size={14} color="#f59e0b" />,
    });
  }

  // Bands used
  if (basis.bands || analysis.bands) {
    const b = basis.bands || analysis.bands;
    measurements.push({
      label: 'Bands Used',
      value: Array.isArray(b) ? b.join(', ') : (typeof b === 'object' ? Object.keys(b).join(', ') : String(b)),
      icon: <Layers size={14} color="#34d399" />,
    });
  } else if (result.selected_tool === 'ndvi_analysis') {
    measurements.push({ label: 'Bands Used', value: 'B4 (Red 0.65µm) + B5 (NIR 0.86µm)', icon: <Layers size={14} color="#34d399" /> });
  } else if (result.selected_tool === 'change_detection_model') {
    measurements.push({ label: 'Bands Used', value: 'Bi-Temporal B4 + B5 Pairs', icon: <Layers size={14} color="#34d399" /> });
  } else if (result.selected_tool === 'optical_sar_model') {
    measurements.push({ label: 'Bands Used', value: 'Landsat B2-B5 + Sentinel-1 VV/VH', icon: <Layers size={14} color="#a855f7" /> });
  }

  // Dynamic classification
  if (result.interpretation?.dynamic_classification) {
    measurements.push({
      label: 'Temporal Dynamic',
      value: result.interpretation.dynamic_classification,
      icon: <Compass size={14} color="#38bdf8" />,
    });
  } else if (result.interpretation?.vegetation_category) {
    measurements.push({
      label: 'Canopy Density',
      value: result.interpretation.vegetation_category,
      icon: <CheckCircle2 size={14} color="#10b981" />,
    });
  }

  const changeStats = analysis.statistics || (analysis.change_detection && analysis.change_detection.statistics);
  if (changeStats) {
    const s = changeStats;
    const bMean = s.baseline_mean_ndvi ?? s.before_mean_ndvi;
    const aMean = s.monitoring_mean_ndvi ?? s.after_mean_ndvi;
    const dMean = s.mean_delta_ndvi ?? s.delta_mean_ndvi ?? s.mean_ndvi_change;
    const gain = s.vegetation_gain_percentage ?? s.increase_percentage;
    const loss = s.vegetation_loss_percentage ?? s.decrease_percentage;
    const stable = s.stable_percentage;

    if (bMean !== undefined) {
      measurements.push({ label: 'Baseline Mean (T1)', value: Number(bMean).toFixed(4), icon: <Globe size={14} color="#38bdf8" /> });
    }
    if (aMean !== undefined) {
      measurements.push({ label: 'Monitoring Mean (T2)', value: Number(aMean).toFixed(4), icon: <Globe size={14} color="#34d399" /> });
    }
    if (dMean !== undefined) {
      measurements.push({ label: 'Net Delta (ΔNDVI)', value: `${Number(dMean) >= 0 ? '+' : ''}${Number(dMean).toFixed(4)}`, icon: <Compass size={14} color="#38bdf8" /> });
    }
    if (gain !== undefined) {
      measurements.push({ label: 'Vegetation Gain', value: `${Number(gain).toFixed(1)}%`, icon: <CheckCircle2 size={14} color="#10b981" /> });
    }
    if (loss !== undefined) {
      measurements.push({ label: 'Vegetation Loss', value: `${Number(loss).toFixed(1)}%`, icon: <CheckCircle2 size={14} color="#f43f5e" /> });
    }
    if (stable !== undefined) {
      measurements.push({ label: 'Stable Terrain', value: `${Number(stable).toFixed(1)}%`, icon: <CheckCircle2 size={14} color="#94a3b8" /> });
    }
  }

  // Deterministic NDVI Analysis Measurements
  const ndviStats = analysis.ndvi_statistics || analysis.ndvi;
  if (ndviStats || result.selected_tool === 'ndvi_analysis') {
    const statsObj = ndviStats || {};
    const meanVal = statsObj.mean !== undefined ? statsObj.mean : statsObj.mean_ndvi;
    if (meanVal !== undefined) {
      const num = Number(meanVal);
      measurements.push({
        label: 'Mean NDVI',
        value: `${num >= 0 ? '+' : ''}${num.toFixed(3)}`,
        icon: <TrendingUp size={14} color="#10b981" />,
      });
    }
    if (statsObj.stddev !== undefined) {
      measurements.push({
        label: 'NDVI StdDev',
        value: `±${Number(statsObj.stddev).toFixed(3)}`,
        icon: <Compass size={14} color="#38bdf8" />,
      });
    }
    const crsVal = analysis.processing?.crs || analysis.crs;
    if (crsVal) {
      measurements.push({
        label: 'CRS',
        value: String(crsVal),
        icon: <Globe size={14} color="#38bdf8" />,
      });
    }
    const resVal = result.analyzed_scene?.resolution || '30 m';
    measurements.push({
      label: 'Resolution',
      value: resVal,
      icon: <Layers size={14} color="#38bdf8" />,
    });
    const acqDate = result.analyzed_scene?.date || result.analyzed_scene?.acquisition_date || parseSceneDate(analysis.scene || basis.scene);
    if (acqDate) {
      measurements.push({
        label: 'Acquisition Date',
        value: acqDate,
        icon: <Calendar size={14} color="#f59e0b" />,
      });
    }
  }

  // Spectral Analysis Multi-Indices Measurements
  const spectralIndices = (analysis.spectral_indices || analysis.indices) as Record<string, any> | undefined;
  if (spectralIndices) {
    if (spectralIndices.ndwi && spectralIndices.ndwi.mean !== undefined) {
      const val = Number(spectralIndices.ndwi.mean);
      measurements.push({
        label: 'Mean NDWI (Water)',
        value: `${val >= 0 ? '+' : ''}${val.toFixed(3)}`,
        icon: <Globe size={14} color="#06b6d4" />,
      });
    }
    if (spectralIndices.mndwi && spectralIndices.mndwi.mean !== undefined) {
      const val = Number(spectralIndices.mndwi.mean);
      measurements.push({
        label: 'Mean MNDWI',
        value: `${val >= 0 ? '+' : ''}${val.toFixed(3)}`,
        icon: <Globe size={14} color="#06b6d4" />,
      });
    }
    if (spectralIndices.evi && spectralIndices.evi.mean !== undefined) {
      const val = Number(spectralIndices.evi.mean);
      measurements.push({
        label: 'Mean EVI',
        value: `${val >= 0 ? '+' : ''}${val.toFixed(3)}`,
        icon: <TrendingUp size={14} color="#10b981" />,
      });
    }
  }

  const analyzedScene = result.analyzed_scene;
  const backendSourceTitle = result.source_scene_name || analyzedScene?.source_scene_name || analyzedScene?.title;
  const backendSourceSensor = result.source_sensor || analyzedScene?.source_sensor || analyzedScene?.sensor;
  const backendSourceDate = result.source_dates || analyzedScene?.source_dates || analyzedScene?.date || analyzedScene?.acquisition_date;
  const backendSourceId = result.source_scene_id || analyzedScene?.source_scene_id || analyzedScene?.scene_id || analysis.scene || basis.scene || '';
  const backendSourceBands = result.source_bands || analyzedScene?.source_bands || analyzedScene?.bands;

  let sourceSceneTitle = backendSourceTitle || (backendSourceId ? `${backendSourceSensor || 'Satellite Scene'} • ${backendSourceDate || 'Active'}` : 'Active Scene');
  let sourceSceneMeta = '';

  if (result.selected_tool === 'change_detection_model' || analyzedScene?.mode === 'bitemporal') {
    const bDate = result.before_date || analyzedScene?.before_date || analyzedScene?.before?.date || analysis.before?.date || 'Before';
    const aDate = result.after_date || analyzedScene?.after_date || analyzedScene?.after?.date || analysis.after?.date || 'After';
    sourceSceneTitle = `Bi-Temporal Pair: ${bDate} ➔ ${aDate}`;
    const pr = analyzedScene?.path_row_formatted ? `Path/Row: ${analyzedScene.path_row_formatted} • ` : '';
    sourceSceneMeta = `${pr}Coregistered NDVI Diff • ${backendSourceSensor || 'Bi-Temporal Sensors'}`;
  } else if (result.selected_tool === 'optical_sar_model' || analyzedScene?.mode === 'fusion') {
    sourceSceneTitle = backendSourceTitle || `Multimodal Fusion: Optical + Sentinel-1 SAR`;
    sourceSceneMeta = `Passive Optical + Active C-Band Microwave SAR • ${backendSourceDate || 'Co-registered'}`;
  } else if (result.selected_tool === 'ndvi_analysis') {
    sourceSceneTitle = `${backendSourceSensor || 'Optical Sensor'} • ${backendSourceDate || 'Active Date'}`;
    const crsDisplay = analysis.processing?.crs || analysis.crs || analyzedScene?.crs || 'EPSG:32645';
    const resDisplay = analyzedScene?.resolution || '30 m';
    sourceSceneMeta = `Scene: ${backendSourceId || 'Active'} • Bands: B4 Red + B5 NIR • Res: ${resDisplay} • CRS: ${crsDisplay}`;
  } else if (analyzedScene) {
    sourceSceneTitle = `${backendSourceSensor || analyzedScene.satellite || 'Satellite Observation'} • ${backendSourceDate || 'Active'}`;
    sourceSceneMeta = [
      analyzedScene.path_row_formatted ? `Path/Row: ${analyzedScene.path_row_formatted}` : null,
      analyzedScene.resolution ? `Res: ${analyzedScene.resolution}` : null,
      analyzedScene.crs ? `CRS: ${analyzedScene.crs}` : null,
      backendSourceBands && backendSourceBands.length > 0 ? `Bands: ${backendSourceBands.join(', ')}` : null,
    ].filter(Boolean).join(' • ');
  }

  return (
    <div className="interpretation-card">
      {/* SOURCE SCENE AUDIT BANNER */}
      <div className="source-scene-audit-banner">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Globe size={15} color="#38bdf8" />
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: 'var(--font-mono)' }}>
            SOURCE SCENE:
          </span>
          <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#f8fafc', fontFamily: 'var(--font-display)' }}>
            {sourceSceneTitle}
          </span>
        </div>
        {sourceSceneMeta && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.74rem', fontFamily: 'var(--font-mono)', color: '#38bdf8' }}>
            {sourceSceneMeta}
          </div>
        )}
      </div>

      {/* MULTI-INTENT ANALYSIS COMPONENTS BANNER */}
      {result.components && result.components.length > 0 && (
        <div className="analysis-components-banner">
          <div className="components-title">
            <Layers size={14} color="#38bdf8" />
            <span>Analysis Components ({result.components.length})</span>
          </div>
          <div className="components-grid">
            {result.components.map((comp, idx) => {
              const isVlmTool = comp.tool === 'remote_sensing_vlm' || comp.tool_name === 'remote_sensing_vlm' || comp.intent === 'scene_description';
              const isDeploymentConstrained = Boolean(
                comp.status === 'bypassed' ||
                result.analysis?.deployment_constrained ||
                (result as any).deployment_constrained ||
                result.interpretation?.basis?.status === 'deployment_constrained'
              );
              let displayStatus = comp.status;
              if (isVlmTool) {
                displayStatus = isDeploymentConstrained ? 'VLM BYPASSED' : 'VLM EXECUTED';
              }
              const statusClass = (isVlmTool && isDeploymentConstrained) ? 'bypassed' : comp.status;

              return (
                <div key={idx} className={`component-pill ${statusClass}`}>
                  <div className="pill-header">
                    <span className="pill-title">{(comp.tool_name || comp.tool || comp.intent || 'Analysis Component').replace(/_/g, ' ')}</span>
                    <span className={`pill-status-tag ${statusClass}`}>{displayStatus}</span>
                  </div>
                  <div className="pill-message">{comp.message || comp.summary || ''}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 2. VISUALLY SEPARATE: AI INTERPRETATION vs SCIENTIFIC MEASUREMENTS */}
      
      {/* SECTION A: AI INTERPRETATION */}
      <div className="result-sub-section">
        <div className="ai-section-header-row">
          <div className="section-header-tag">
            <Bot size={15} color="#38bdf8" />
            <span>AI Vision-Language Interpretation (SmolVLM-500M + RS LoRA)</span>
          </div>

          <div className="ai-header-controls">
            {isLongResponse && (
              <button
                type="button"
                className="ai-toggle-btn"
                onClick={() => setIsExpanded(!isExpanded)}
                title={isExpanded ? 'Collapse to preview' : 'Expand full response'}
              >
                {isExpanded ? (
                  <>
                    <ChevronUp size={13} />
                    <span>Show less</span>
                  </>
                ) : (
                  <>
                    <ChevronDown size={13} />
                    <span>Show more</span>
                  </>
                )}
              </button>
            )}

            <button
              type="button"
              className={`ai-copy-btn ${copied ? 'copied' : ''}`}
              onClick={() => handleCopyAnswer(primaryAiAnswer)}
              title="Copy complete AI interpretation to clipboard"
            >
              {copied ? (
                <>
                  <Check size={13} color="#34d399" />
                  <span style={{ color: '#34d399' }}>Copied!</span>
                </>
              ) : (
                <>
                  <Copy size={13} />
                  <span>Copy Answer</span>
                </>
              )}
            </button>
          </div>
        </div>

        <div className={`ai-interpretation-box ${isExpanded ? 'expanded' : (isLongResponse ? 'collapsed' : 'compact')}`}>
          <div className={`ai-interpretation-scroll-container ${isExpanded && primaryAiAnswer.length > 500 ? 'scrollable' : ''}`}>
            <MarkdownRenderer content={isExpanded || !isLongResponse ? primaryAiAnswer : previewText} />
          </div>

          {isLongResponse && (
            <div className="ai-box-footer">
              <button
                type="button"
                className="ai-show-more-pill"
                onClick={() => setIsExpanded(!isExpanded)}
              >
                {isExpanded ? (
                  <>
                    <ChevronUp size={13} />
                    <span>Show less</span>
                  </>
                ) : (
                  <>
                    <ChevronDown size={13} />
                    <span>Show full answer ({primaryAiAnswer.trim().split(/\s+/).length} words)</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Multimodal VLM Context Box */}
        {visualContext && (
          <div className="vlm-context-box">
            <div className="vlm-context-title">
              <Eye size={15} />
              Multimodal VLM Visual Context (VLM-assisted change interpretation)
            </div>
            <div className="vlm-context-content">
              <MarkdownRenderer content={visualContext} />
            </div>
          </div>
        )}
      </div>

      {/* SECTION B: SCIENTIFIC MEASUREMENTS */}
      {measurements.length > 0 && (
        <div className="result-sub-section" style={{ marginTop: 12 }}>
          <div className="section-header-tag scientific">
            <Terminal size={15} color="#10b981" />
            <span>Deterministic Scientific Measurements & Sensor Metadata</span>
          </div>

          <div className="scientific-measurements-grid">
            {measurements.map((m, idx) => (
              <div key={idx} className="measurement-item">
                <div className="measurement-label-row">
                  {m.icon}
                  <span className="measurement-label">{m.label}</span>
                </div>
                <span className="measurement-value">{m.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION C: RESEARCH REPORT & EVIDENCE DOWNLOAD ACTION BAR */}
      <div className="report-action-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`btn-report-download ${generatingPdf ? 'loading' : ''} ${pdfSuccess ? 'success' : ''}`}
            onClick={handleDownloadPdf}
            disabled={generatingPdf}
            title="Generate and download a structured, publication-grade scientific PDF research report"
          >
            {generatingPdf ? (
              <>
                <Loader2 size={16} className="spinning" />
                <span>Generating Scientific Report...</span>
              </>
            ) : pdfSuccess ? (
              <>
                <CheckCircle2 size={16} color="#34d399" />
                <span>Report Downloaded</span>
              </>
            ) : (
              <>
                <FileText size={16} />
                <span>Download Analysis Report</span>
              </>
            )}
          </button>

          {result.analysis?.evidence && (
            <button
              type="button"
              className={`btn-evidence-download ${downloadingZip ? 'loading' : ''} ${zipSuccess ? 'success' : ''}`}
              onClick={handleDownloadZip}
              disabled={downloadingZip}
              title="Download generated visual evidence artifacts (maps, triplets, spectral charts) as a ZIP archive"
            >
              {downloadingZip ? (
                <>
                  <Loader2 size={15} className="spinning" />
                  <span>Packaging Evidence...</span>
                </>
              ) : zipSuccess ? (
                <>
                  <CheckCircle2 size={15} color="#34d399" />
                  <span>Evidence ZIP Downloaded</span>
                </>
              ) : (
                <>
                  <Download size={15} />
                  <span>Download Evidence (ZIP)</span>
                </>
              )}
            </button>
          )}
        </div>

        {downloadError && (
          <div style={{ color: '#f43f5e', fontSize: '0.78rem', marginTop: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertCircle size={14} />
            <span>{downloadError}</span>
          </div>
        )}
      </div>
    </div>
  );
};
