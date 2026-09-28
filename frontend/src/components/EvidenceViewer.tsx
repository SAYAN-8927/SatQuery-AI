import React, { useState } from 'react';
import { Image as ImageIcon, Maximize2, X, Download, ZoomIn, AlertTriangle, ExternalLink } from 'lucide-react';
import type { Evidence } from '../types';
import { resolveArtifactUrl } from '../api';

interface EvidenceViewerProps {
  evidence?: Evidence;
  selectedTool?: string;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ evidence }) => {
  const [activeModalImage, setActiveModalImage] = useState<{ url: string; title: string; subtitle?: string } | null>(null);
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});

  if (!evidence || Object.keys(evidence).length === 0) {
    return null;
  }

  const imageEntries: {
    key: string;
    title: string;
    subtitle: string;
    url: string;
    badge: string;
    isPrimary?: boolean;
    rawPath?: string;
  }[] = [];

  // 1. Bi-Temporal Triplet
  if (evidence.comparison_triplet) {
    imageEntries.push({
      key: 'triplet',
      title: '3-Panel Bi-Temporal Comparative Triplet',
      subtitle: 'Panel 1: Before NDVI | Panel 2: After NDVI | Panel 3: Calibrated Difference Heatmap',
      url: evidence.comparison_triplet,
      badge: 'Bi-Temporal Triplet (3-Panel)',
      isPrimary: true,
      rawPath: (evidence as any).triplet_disk_path,
    });
  }

  // 2. Optical + SAR Fusion Composite
  if (evidence.fusion_composite) {
    imageEntries.push({
      key: 'fusion',
      title: '4-Panel Optical + SAR Multimodal Fusion Composite',
      subtitle: 'Panel 1: Optical RGB | Panel 2: NDVI Canopy | Panel 3: SAR Radar Backscatter | Panel 4: Environmental Consensus',
      url: evidence.fusion_composite,
      badge: 'Multimodal Fusion Composite (4-Panel)',
      isPrimary: true,
      rawPath: (evidence as any).composite_disk_path,
    });
  }

  // 3. Spectral Profile Reflectance Signature
  if (evidence.spectral_profile_chart) {
    imageEntries.push({
      key: 'spectral',
      title: '4-Band Surface Reflectance Spectral Signature Chart',
      subtitle: 'Central Wavelengths: B2 (0.48µm), B3 (0.56µm), B4 (0.65µm), B5 (0.86µm) with NDWI & NDVI Markers',
      url: evidence.spectral_profile_chart,
      badge: 'Spectral Signature Profile',
      isPrimary: true,
      rawPath: (evidence as any).chart_disk_path,
    });
  }

  // 4. NDVI Canopy False-Color Map
  if (evidence.ndvi_map) {
    const isLC08 = evidence.ndvi_map.includes('LC08') || ((evidence as any).filename && (evidence as any).filename.includes('LC08'));
    const isLC09 = evidence.ndvi_map.includes('LC09') || ((evidence as any).filename && (evidence as any).filename.includes('LC09'));
    const sensorTitle = isLC08 ? 'Landsat-8 OLI' : (isLC09 ? 'Landsat-9 OLI-2' : 'Landsat');

    imageEntries.push({
      key: 'ndvi',
      title: `${sensorTitle} Surface Reflectance NDVI Spatial Map`,
      subtitle: 'Calibrated color scale: Water/Non-veg (-1.0 to 0.0) → Sparse/Soil (0.0 to 0.2) → Moderate (0.2 to 0.5) → Dense Canopy (> 0.5)',
      url: evidence.ndvi_map,
      badge: 'Calibrated NDVI Spatial Map',
      isPrimary: !evidence.comparison_triplet,
      rawPath: (evidence as any).ndvi_map_disk_path,
    });
  }

  // 5. Change Map (if triplet not present)
  if (evidence.change_map && !evidence.comparison_triplet) {
    imageEntries.push({
      key: 'change_map',
      title: 'Bi-Temporal Vegetation Gain / Loss Difference Heatmap',
      subtitle: 'Green: Net Gain (> +0.10) | Red: Net Loss (< -0.10) | Gray: Stable Terrain',
      url: evidence.change_map,
      badge: 'NDVI Difference Map',
      isPrimary: true,
    });
  }

  // 6. Generic VLM or Single-Image Visual Evidence
  const vlmImg = (evidence as any).vlm_evidence || (evidence as any).image_preview || (evidence as any).visual_evidence;
  if (vlmImg && imageEntries.length === 0) {
    imageEntries.push({
      key: 'vlm_evidence',
      title: 'Single-Image Visual Evidence Inspection',
      subtitle: 'Visual raster input analyzed by Fine-Tuned Remote Sensing VLM',
      url: vlmImg,
      badge: 'Input Visual Evidence',
      isPrimary: true,
    });
  }

  if (imageEntries.length === 0) return null;

  return (
    <div className="evidence-card prominent">
      <div className="evidence-title-row">
        <div className="evidence-title">
          <ImageIcon size={22} color="#38bdf8" />
          <span>Visual Scientific Evidence ({imageEntries.length} Generated Artifact{imageEntries.length > 1 ? 's' : ''})</span>
        </div>
        <div className="evidence-controls-hint">
          <ZoomIn size={14} color="#38bdf8" />
          <span>Click any raster to open high-resolution inspection lightbox</span>
        </div>
      </div>

      <div className="evidence-prominent-grid">
        {imageEntries.map((item) => {
          const resolvedUrl = resolveArtifactUrl(item.url);
          const hasError = !!failedImages[item.key];

          return (
            <div
              key={item.key}
              className={`evidence-prominent-box ${item.isPrimary ? 'primary-artifact' : ''}`}
              onClick={() => {
                if (!hasError) {
                  setActiveModalImage({ url: resolvedUrl, title: item.title, subtitle: item.subtitle });
                }
              }}
            >
              <div className="artifact-header-tag">
                <span className="artifact-badge-pill">{item.badge}</span>
                {!hasError && <Maximize2 size={15} className="zoom-icon" />}
              </div>

              <div className="evidence-image-wrapper">
                {hasError ? (
                  <div className="evidence-fallback-box" onClick={(e) => e.stopPropagation()}>
                    <AlertTriangle size={24} color="#f59e0b" />
                    <p className="evidence-fallback-title">
                      {item.badge} generated, but visual preview could not be loaded.
                    </p>
                    <div className="evidence-fallback-actions">
                      <a
                        href={resolvedUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="btn-open-evidence"
                      >
                        <ExternalLink size={14} />
                        Open Evidence
                      </a>
                    </div>
                    <details className="evidence-technical-details">
                      <summary>Technical Details</summary>
                      <div className="technical-details-content">
                        <div><strong>Artifact Key:</strong> {item.key}</div>
                        <div><strong>Backend URL:</strong> {item.url}</div>
                        <div><strong>Browser URL:</strong> {resolvedUrl}</div>
                        {item.rawPath && <div><strong>Disk Path:</strong> {item.rawPath}</div>}
                      </div>
                    </details>
                  </div>
                ) : (
                  <img
                    src={resolvedUrl}
                    alt={item.title}
                    loading="lazy"
                    onError={() => {
                      setFailedImages((prev) => ({ ...prev, [item.key]: true }));
                    }}
                  />
                )}
              </div>

              <div className="artifact-meta-footer">
                <h4 className="artifact-title-text">{item.title}</h4>
                <p className="artifact-subtitle-text">{item.subtitle}</p>

                {/* Explicit Scientific Legend for NDVI Maps */}
                {item.key === 'ndvi' && (
                  <div className="evidence-legend-box">
                    <div className="legend-title">Calibrated NDVI Legend:</div>
                    <div className="legend-items">
                      <span className="legend-item">
                        <span className="legend-dot water" />
                        -1.0 → non-vegetation / water
                      </span>
                      <span className="legend-item">
                        <span className="legend-dot sparse" />
                        0.0 → sparse or mixed vegetation
                      </span>
                      <span className="legend-item">
                        <span className="legend-dot dense" />
                        higher positive values → stronger vegetation signal
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Lightbox Modal */}
      {activeModalImage && (
        <div className="lightbox-backdrop" onClick={() => setActiveModalImage(null)}>
          <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
            <button className="lightbox-close-btn" onClick={() => setActiveModalImage(null)}>
              <X size={20} />
            </button>
            <img src={activeModalImage.url} alt={activeModalImage.title} className="lightbox-image" />
            <div className="lightbox-footer">
              <div>
                <p className="lightbox-footer-title">{activeModalImage.title}</p>
                {activeModalImage.subtitle && (
                  <p className="lightbox-footer-sub">{activeModalImage.subtitle}</p>
                )}
              </div>
              <a
                href={activeModalImage.url}
                download
                className="submit-btn"
                style={{ padding: '8px 18px', fontSize: '0.82rem' }}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={14} />
                Download GeoTIFF Artifact
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

