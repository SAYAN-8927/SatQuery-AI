import React, { useRef, useState } from 'react';
import { Layers, UploadCloud, Calendar, CheckCircle2, AlertCircle, RefreshCw, Radio, Globe, Trash2, ShieldCheck } from 'lucide-react';
import type { SceneData, UploadResponse, SceneInfo, MultimodalPair } from '../types';
import { uploadImage } from '../api';

interface SceneSidebarProps {
  sceneData: SceneData | null;
  loading: boolean;
  selectedSceneId: string | null;
  onRefresh: () => void;
  onUploadSuccess: (res: UploadResponse) => void;
  onSelectBand: (sceneId: string, band: string) => void;
  onSelectScene: (sceneId: string) => void;
  onSelectBiTemporal?: (pair: any) => void;
  isBiTemporalActive?: boolean;
  multimodalPair?: MultimodalPair | null;
  onSelectMultimodal?: (pair: any) => void;
  isMultimodalActive?: boolean;
  onRequestDeleteScene?: (scene: SceneInfo) => void;
  onRequestClearWorkspace?: () => void;
}

export const SceneSidebar: React.FC<SceneSidebarProps> = ({
  sceneData,
  loading,
  selectedSceneId,
  onRefresh,
  onUploadSuccess,
  onSelectBand,
  onSelectScene,
  onSelectBiTemporal,
  isBiTemporalActive = false,
  multimodalPair,
  onSelectMultimodal,
  isMultimodalActive = false,
  onRequestDeleteScene,
  onRequestClearWorkspace,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleFiles = async (files: File[]) => {
    if (!files || files.length === 0) return;
    try {
      setUploading(true);
      setUploadMessage(null);
      let lastRes: UploadResponse | null = null;
      for (const file of files) {
        lastRes = await uploadImage(file);
      }
      if (lastRes) {
        const count = files.length;
        setUploadMessage({
          type: 'success',
          text: count > 1
            ? `Successfully ingested ${count} band files for scene!`
            : `Ingested ${files[0].name}: ${lastRes.classification?.satellite || 'Remote sensing data'} identified!`,
        });
        onUploadSuccess(lastRes);
      }
    } catch (err: any) {
      setUploadMessage({
        type: 'error',
        text: err.message || 'Upload failed',
      });
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const pair = sceneData?.bi_temporal_pairs && sceneData.bi_temporal_pairs.length > 0 ? sceneData.bi_temporal_pairs[0] : null;

  return (
    <aside className="scene-sidebar">
      {/* Fixed Compact Sensor Catalog Header */}
      <div className="sidebar-header-bar">
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: '0.8rem', color: 'var(--text-primary)' }}>
          <Layers size={16} color="#38bdf8" />
          Sensor Catalog ({sceneData?.scenes?.length || 0})
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {onRequestClearWorkspace && (sceneData?.scenes?.length || 0) > 0 && (
            <button
              type="button"
              className="clear-workspace-btn"
              onClick={onRequestClearWorkspace}
              title="Clear all datasets from current workspace"
            >
              <Trash2 size={11} />
              <span>Clear</span>
            </button>
          )}
          <button
            onClick={onRefresh}
            title="Refresh Ingested Scenes"
            style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
          >
            <RefreshCw size={14} className={loading ? 'spinning' : ''} />
          </button>
        </div>
      </div>

      {/* Main Scrollable Area with Scrollbar on the Right for Uploaded Images & Scenes */}
      <div className="scenes-scroll-container">
        {/* Multimodal Optical + SAR Pair Card */}
        {multimodalPair && (
          <div
            className="multimodal-card-enhanced"
            onClick={() => onSelectMultimodal?.(multimodalPair)}
            style={{
              cursor: 'pointer',
              borderColor: isMultimodalActive ? '#38bdf8' : 'rgba(56, 189, 248, 0.3)',
              boxShadow: isMultimodalActive ? '0 0 16px rgba(56,189,248,0.25), inset 0 0 8px rgba(168,85,247,0.12)' : undefined,
              marginBottom: 12,
            }}
            title="Click to select this Optical + SAR multimodal pair as active analysis context"
          >
            <div className="multimodal-title-badge" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Layers size={13} color="#38bdf8" />
                <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.8rem' }}>Optical + SAR Pair</span>
              </div>
              {isMultimodalActive ? (
                <span className="selected-scene-pill" style={{ borderColor: '#38bdf8', color: '#38bdf8', background: 'rgba(56,189,248,0.18)' }}>
                  <CheckCircle2 size={10} />
                  Active Pair
                </span>
              ) : (
                <span style={{ fontSize: '0.68rem', color: '#38bdf8', background: 'rgba(56,189,248,0.12)', padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>
                  {multimodalPair.location}
                </span>
              )}
            </div>

            <div className="bitemporal-timeline-row" style={{ marginTop: 8 }}>
              {/* Optical Node */}
              <div className="temporal-node">
                <span className="temporal-tag" style={{ background: 'rgba(56,189,248,0.18)', color: '#38bdf8' }}>OPTICAL</span>
                <span className="temporal-date">{multimodalPair.optical_acquisition_date || '19 Apr 2026'}</span>
                <span className="temporal-sat">{multimodalPair.optical_satellite || 'Landsat-9'}</span>
                <span className="temporal-pathrow" style={{ fontSize: '0.68rem', color: '#94a3b8', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                  B2-B5 Multispectral
                </span>
              </div>

              {/* Temporal Gap Connector */}
              <div className="temporal-arrow-box">
                <span className="interval-days-pill" style={{ background: 'rgba(168,85,247,0.2)', color: '#c084fc', border: '1px solid rgba(168,85,247,0.4)' }}>
                  {multimodalPair.temporal_gap_days}d gap
                </span>
                <div className="temporal-connector-line" style={{ background: 'linear-gradient(90deg, #38bdf8, #a855f7)' }} />
              </div>

              {/* SAR Node */}
              <div className="temporal-node">
                <span className="temporal-tag" style={{ background: 'rgba(168,85,247,0.18)', color: '#c084fc' }}>SAR RADAR</span>
                <span className="temporal-date">{multimodalPair.sar_acquisition_date || '13 Apr 2026'}</span>
                <span className="temporal-sat">{multimodalPair.sar_satellite || 'Sentinel-1A'}</span>
                <span className="temporal-pathrow" style={{ fontSize: '0.68rem', color: '#94a3b8', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                  VV + VH Dual-Pol
                </span>
              </div>
            </div>

            {/* Visual Mini Previews for Optical and SAR */}
            {(multimodalPair.optical_preview || multimodalPair.sar_preview) && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 8 }}>
                {multimodalPair.optical_preview && (
                  <div style={{ height: 48, borderRadius: 4, overflow: 'hidden', border: '1px solid rgba(56,189,248,0.25)', background: '#040814' }}>
                    <img src={multimodalPair.optical_preview} alt="Optical" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={(e) => { const p = (e.currentTarget as HTMLElement).parentElement; if (p) p.style.display = 'none'; }} />
                  </div>
                )}
                {multimodalPair.sar_preview && (
                  <div style={{ height: 48, borderRadius: 4, overflow: 'hidden', border: '1px solid rgba(168,85,247,0.25)', background: '#040814' }}>
                    <img src={multimodalPair.sar_preview} alt="SAR" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={(e) => { const p = (e.currentTarget as HTMLElement).parentElement; if (p) p.style.display = 'none'; }} />
                  </div>
                )}
              </div>
            )}

            <div className="bitemporal-footer-info" style={{ marginTop: 6, paddingTop: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <CheckCircle2 size={11} color="#38bdf8" />
                <span>Coregistered: {multimodalPair.location}</span>
              </div>
              <button
                type="button"
                className="select-pair-btn"
                style={{
                  background: isMultimodalActive ? 'rgba(56,189,248,0.2)' : 'rgba(255,255,255,0.06)',
                  border: isMultimodalActive ? '1px solid #38bdf8' : '1px solid rgba(255,255,255,0.15)',
                  color: isMultimodalActive ? '#38bdf8' : '#e2e8f0',
                  fontSize: '0.68rem',
                  padding: '2px 8px',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontWeight: 600
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectMultimodal?.(multimodalPair);
                }}
              >
                {isMultimodalActive ? 'Selected' : 'Select Pair'}
              </button>
            </div>
          </div>
        )}

        {/* Bi-Temporal Analysis Card (Scrolls with scenes) */}
        {pair && (
          <div
            className="bitemporal-card-enhanced"
            onClick={() => onSelectBiTemporal?.(pair)}
            style={{
              cursor: 'pointer',
              borderColor: isBiTemporalActive ? '#10b981' : undefined,
              boxShadow: isBiTemporalActive ? '0 0 16px rgba(16,185,129,0.22), inset 0 0 8px rgba(16,185,129,0.08)' : undefined,
              marginBottom: 12,
            }}
            title="Click to select this bi-temporal pair as active change detection context"
          >
            <div className="bitemporal-title-badge" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Calendar size={13} color="#10b981" />
                <span>Automatic Temporal Pair</span>
              </div>
              {isBiTemporalActive && (
                <span className="selected-scene-pill" style={{ borderColor: '#10b981', color: '#10b981', background: 'rgba(16,185,129,0.18)' }}>
                  <CheckCircle2 size={10} />
                  Active Pair
                </span>
              )}
            </div>

            <div className="bitemporal-timeline-row">
              <div className="temporal-node">
                <span className="temporal-tag">BEFORE</span>
                <span className="temporal-date">{pair.before_date || pair.before?.acquisition_date || '10 Aug 2026'}</span>
                <span className="temporal-sat">{pair.before?.satellite || 'Landsat-9'}</span>
                <span className="temporal-pathrow" style={{ fontSize: '0.68rem', color: '#94a3b8', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                  {pair.before?.path_row_formatted || pair.path_row_formatted || '141/040'}
                </span>
              </div>

              <div className="temporal-arrow-box">
                <span className="interval-days-pill">{pair.interval_days || 16}d</span>
                <div className="temporal-connector-line" />
              </div>

              <div className="temporal-node">
                <span className="temporal-tag after">AFTER</span>
                <span className="temporal-date">{pair.after_date || pair.after?.acquisition_date || '26 Aug 2026'}</span>
                <span className="temporal-sat">{pair.after?.satellite || 'Landsat-9'}</span>
                <span className="temporal-pathrow" style={{ fontSize: '0.68rem', color: '#94a3b8', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                  {pair.after?.path_row_formatted || pair.path_row_formatted || '141/040'}
                </span>
              </div>
            </div>

            <div className="bitemporal-footer-info" style={{ marginTop: 6, paddingTop: 6 }}>
              <CheckCircle2 size={11} color="#34d399" />
              <span>Coregistered: Path/Row {pair.path_row_formatted || '141/040'} • B4+B5</span>
            </div>
          </div>
        )}

        <div className="sidebar-title" style={{ fontSize: '0.75rem', marginBottom: 10 }}>
          <span>Active Satellite Scenes</span>
          {sceneData?.scenes && sceneData.scenes.length > 0 && (
            <span className="scene-count-badge">
              {sceneData.scenes.length}
            </span>
          )}
        </div>

        {sceneData?.scenes?.map((scene) => {
          const isSelected = scene.scene_id === selectedSceneId;
          return (
            <div
              key={scene.scene_id}
              className={`scene-card-enhanced ${scene.modality} ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelectScene(scene.scene_id)}
              style={{ cursor: 'pointer' }}
              title={`Click to set ${scene.satellite || 'this scene'} as active query context`}
            >
              <div className="scene-card-top-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {scene.modality === 'sar' ? (
                    <Radio size={14} color="#a855f7" />
                  ) : (
                    <Globe size={14} color="#38bdf8" />
                  )}
                  <span className="scene-satellite-name">{scene.satellite || (scene.modality === 'sar' ? 'SENTINEL-1A' : 'LANDSAT-9')}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {isSelected && (
                    <span className="selected-scene-pill">
                      <CheckCircle2 size={10} />
                      Selected
                    </span>
                  )}
                  <span className={`modality-pill ${scene.modality}`}>
                    {scene.modality.toUpperCase()}
                  </span>
                </div>
              </div>

              <div className="scene-sensor-name">
                {scene.sensor || (scene.modality === 'sar' ? 'C-SAR Active Radar' : 'OLI-2 Operational Land Imager')}
              </div>

              <div className="scene-id-code" title={scene.scene_id}>
                {scene.scene_id}
              </div>

              {/* Visual Thumbnail Preview for Uploaded Images / Screenshots */}
              {(scene.thumbnail_url || scene.thumbnail) && (
                <div
                  style={{
                    width: '100%',
                    height: '76px',
                    borderRadius: '6px',
                    overflow: 'hidden',
                    marginBottom: '8px',
                    background: '#040814',
                    border: '1px solid rgba(56, 189, 248, 0.25)',
                    position: 'relative',
                  }}
                >
                  <img
                    src={scene.thumbnail_url || scene.thumbnail}
                    alt={scene.scene_id}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={(e) => {
                      const parent = (e.currentTarget as HTMLElement).parentElement;
                      if (parent) parent.style.display = 'none';
                    }}
                  />
                </div>
              )}

              {/* Metadata Specs Grid */}
              {scene.is_generic_image ? (
                <div className="scene-specs-grid">
                  <div className="spec-cell">
                    <span className="spec-key">Format:</span>
                    <span className="spec-val" style={{ color: '#38bdf8', fontWeight: 600 }}>{scene.image_format || 'PNG'}</span>
                  </div>
                  <div className="spec-cell">
                    <span className="spec-key">Channels:</span>
                    <span className="spec-val">{scene.channels || 'RGB'}</span>
                  </div>
                  <div className="spec-cell">
                    <span className="spec-key">Dimensions:</span>
                    <span className="spec-val">{scene.dimensions || 'Standard'}</span>
                  </div>
                  <div className="spec-cell">
                    <span className="spec-key">Uploaded:</span>
                    <span className="spec-val">{scene.acquisition_date || 'Active'}</span>
                  </div>
                  <div className="spec-cell" style={{ gridColumn: 'span 2' }}>
                    <span className="spec-key">Geospatial:</span>
                    <span className="spec-val" style={{ color: '#94a3b8' }}>Not available</span>
                  </div>
                </div>
              ) : (
                <div className="scene-specs-grid">
                  <div className="spec-cell">
                    <span className="spec-key">Date:</span>
                    <span className="spec-val">{scene.acquisition_date || 'Active Scene'}</span>
                  </div>
                  {scene.path_row_formatted ? (
                    <div className="spec-cell">
                      <span className="spec-key">Path/Row:</span>
                      <span className="spec-val" style={{ color: '#38bdf8', fontWeight: 600 }}>{scene.path_row_formatted}</span>
                    </div>
                  ) : (
                    <div className="spec-cell">
                      <span className="spec-key">Resolution:</span>
                      <span className="spec-val">{scene.resolution || '30 m'}</span>
                    </div>
                  )}
                  {scene.path_row_formatted && (
                    <div className="spec-cell">
                      <span className="spec-key">Resolution:</span>
                      <span className="spec-val">{scene.resolution || '30 m'}</span>
                    </div>
                  )}
                  <div className="spec-cell" style={scene.path_row_formatted ? {} : { gridColumn: 'span 2' }}>
                    <span className="spec-key">CRS:</span>
                    <span className="spec-val">{scene.crs || 'EPSG:32645'}</span>
                  </div>
                </div>
              )}

              {/* Available Bands & Scene Deletion */}
              <div className="scene-bands-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span className="bands-label">Bands:</span>
                  <div className="band-chips-row">
                    {scene.bands.map((band) => (
                      <button
                        key={band}
                        className="band-chip"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectBand(scene.scene_id, band);
                        }}
                        title={`Click to preview ${band} image (does not change active query scene)`}
                        style={{
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        {band}
                      </button>
                    ))}
                  </div>
                </div>
                {onRequestDeleteScene && (
                  <button
                    type="button"
                    className="scene-delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRequestDeleteScene(scene);
                    }}
                    title={`Delete scene ${scene.satellite || ''} (${scene.bands.length} bands)`}
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Ingestion Dropzone - Fixed at bottom */}
      <div className="sidebar-ingest-footer">
        <div className="sidebar-title" style={{ fontSize: '0.75rem', marginBottom: 8 }}>Ingest Satellite Band / Image</div>

        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          multiple
          accept=".tif,.tiff,.png,.jpg,.jpeg"
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              handleFiles(Array.from(e.target.files));
            }
          }}
        />

        <div
          className={`upload-dropzone ${dragActive ? 'drag-active' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <UploadCloud size={22} className="upload-icon" />
          <p>{uploading ? 'Processing Raster...' : 'Upload GeoTIFF or PNG'}</p>
          <span>Landsat-8/9, Sentinel-1 SAR</span>
        </div>

        {uploadMessage && (
          <div
            style={{
              marginTop: 10,
              padding: 8,
              borderRadius: 6,
              fontSize: '0.72rem',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: uploadMessage.type === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)',
              border: `1px solid ${uploadMessage.type === 'success' ? '#10b981' : '#f43f5e'}`,
              color: uploadMessage.type === 'success' ? '#34d399' : '#fb7185',
            }}
          >
            {uploadMessage.type === 'success' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
            <span>{uploadMessage.text}</span>
          </div>
        )}

        {/* Temporary Workspace Privacy Note */}
        <div className="workspace-privacy-note">
          <ShieldCheck size={13} color="#38bdf8" />
          <span>Uploaded data is stored in your temporary SatQuery workspace.</span>
        </div>
      </div>
    </aside>
  );
};
