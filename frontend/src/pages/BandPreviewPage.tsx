import React, { useEffect, useState } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { fetchScenes } from '../api';
import type { SceneInfo, BandPreview } from '../types';

interface BandPreviewPageProps {
  sceneId: string;
  band: string;
  onBack: () => void;
}

const BAND_METADATA: Record<string, { title: string; desc: string }> = {
  B2: { title: 'B2 — BLUE BAND', desc: '0.48 µm • Coastal & Aerosol Studies' },
  B3: { title: 'B3 — GREEN BAND', desc: '0.56 µm • Vegetation Peak & Water Clearness' },
  B4: { title: 'B4 — RED BAND', desc: '0.65 µm • Chlorophyll Absorption' },
  B5: { title: 'B5 — NEAR INFRARED (NIR)', desc: '0.86 µm • Vegetation Biomass & Canopy Moisture' },
  VV: { title: 'VV — VERTICAL-VERTICAL CO-POLARIZATION', desc: 'C-Band 5.405 GHz • Surface Roughness & Specular Water' },
  VH: { title: 'VH — VERTICAL-HORIZONTAL CROSS-POLARIZATION', desc: 'C-Band 5.405 GHz • Volume Scattering & Canopy Density' },
  RGB: { title: 'RGB — TRUE-COLOR VISUAL IMAGERY', desc: '400-700 nm • Natural Color Remote Sensing Observation' },
};

export const BandPreviewPage: React.FC<BandPreviewPageProps> = ({
  sceneId,
  band,
  onBack,
}) => {
  const bandUpper = band.toUpperCase();
  const isSar = sceneId.startsWith('S1') || bandUpper === 'VV' || bandUpper === 'VH';

  // Compute canonical preview URL immediately
  const getInitialUrl = () => {
    if (bandUpper === 'RGB') {
      return '';
    }
    return isSar
      ? `/uploads/previews/${sceneId}_${bandUpper}_preview.png`
      : `/uploads/previews/${sceneId}_SR_${bandUpper}_preview.png`;
  };

  const [scene, setScene] = useState<SceneInfo | null>(null);
  const [imageUrl, setImageUrl] = useState<string>(getInitialUrl);
  const [imageLoaded, setImageLoaded] = useState<boolean>(false);
  const [imageFailed, setImageFailed] = useState<boolean>(false);

  useEffect(() => {
    // When sceneId or band changes, reset image state
    setImageUrl(getInitialUrl());
    setImageLoaded(false);
    setImageFailed(false);
  }, [sceneId, band]);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      try {
        const data = await fetchScenes();
        if (!isMounted) return;
        const matched = data.scenes.find(
          (s) => s.scene_id === sceneId || sceneId.includes(s.scene_id) || s.scene_id.includes(sceneId)
        );
        if (matched) {
          setScene(matched);
          // If scene has explicit preview_url for this band, use it
          if (matched.band_previews && Array.isArray(matched.band_previews)) {
            const bp = matched.band_previews.find((b: BandPreview) => b.band.toUpperCase() === bandUpper);
            if (bp && bp.preview_url) {
              setImageUrl(bp.preview_url);
            } else if (matched.thumbnail) {
              setImageUrl(matched.thumbnail);
            }
          } else if (matched.thumbnail) {
            setImageUrl(matched.thumbnail);
          }
        }
      } catch (err) {
        console.warn('Metadata lookup notice:', err);
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, [sceneId, bandUpper]);

  const bandInfo = BAND_METADATA[bandUpper] || {
    title: `${bandUpper} BAND`,
    desc: 'Satellite Spectral Raster Band',
  };

  const sceneTitle = scene?.title || (
    scene?.satellite && scene?.acquisition_date
      ? `${scene.satellite} • ${scene.acquisition_date}`
      : (scene?.satellite || (sceneId.startsWith('LC09') ? 'Landsat-9 OLI-2' : (sceneId.startsWith('LC08') ? 'Landsat-8 OLI' : 'Sentinel-1A C-SAR')))
  );

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#050811',
        color: '#f8fafc',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '32px 20px',
        fontFamily: 'var(--font-sans)',
      }}
    >
      {/* Top Bar with Back Button */}
      <div
        style={{
          width: '100%',
          maxWidth: '900px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
        }}
      >
        <button
          onClick={onBack}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            color: '#38bdf8',
            padding: '8px 16px',
            borderRadius: '8px',
            fontSize: '0.85rem',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(56, 189, 248, 0.15)';
            e.currentTarget.style.borderColor = '#38bdf8';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(15, 23, 42, 0.8)';
            e.currentTarget.style.borderColor = 'rgba(56, 189, 248, 0.25)';
          }}
        >
          <ArrowLeft size={16} />
          <span>Back to Dashboard</span>
        </button>

        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
            color: '#64748b',
          }}
        >
          SatQuery AI • Band Preview
        </span>
      </div>

      {/* Main Image Inspection Container */}
      <div
        style={{
          width: '100%',
          maxWidth: '900px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          background: '#0c1527',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          borderRadius: '16px',
          padding: '28px',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
        }}
      >
        {/* Header Titles */}
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '1.45rem',
            fontWeight: 700,
            letterSpacing: '0.04em',
            color: '#f8fafc',
            marginBottom: '4px',
            textAlign: 'center',
          }}
        >
          {bandInfo.title}
        </h1>

        <p
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.85rem',
            color: '#38bdf8',
            marginBottom: '20px',
            textAlign: 'center',
          }}
        >
          {sceneTitle}
        </p>

        {/* The Large Band Image */}
        <div
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#050811',
            borderRadius: '12px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            padding: '16px',
            minHeight: '420px',
            position: 'relative',
          }}
        >
          {!imageLoaded && !imageFailed && (
            <div
              style={{
                position: 'absolute',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '8px',
                color: '#64748b',
                zIndex: 1,
              }}
            >
              <Loader2 size={24} className="spinning" />
              <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                Loading raster preview...
              </span>
            </div>
          )}

          {imageFailed ? (
            <div style={{ color: '#fb7185', fontSize: '0.85rem', fontFamily: 'var(--font-mono)', textAlign: 'center', padding: '24px' }}>
              Preview image not found for {bandUpper}
              <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '6px' }}>{imageUrl}</div>
            </div>
          ) : (
            <img
              src={imageUrl}
              alt={`${bandInfo.title} preview`}
              onLoad={() => setImageLoaded(true)}
              onError={() => {
                // If it was trying _SR_ and failed, try without _SR_, or vice-versa
                if (imageUrl.includes('_SR_')) {
                  setImageUrl(imageUrl.replace('_SR_', '_'));
                } else if (!imageUrl.includes('_SR_') && !isSar) {
                  setImageUrl(imageUrl.replace(`_${bandUpper}_preview`, `_SR_${bandUpper}_preview`));
                } else {
                  setImageFailed(true);
                }
              }}
              style={{
                maxWidth: '100%',
                maxHeight: '68vh',
                objectFit: 'contain',
                borderRadius: '8px',
                boxShadow: '0 8px 24px rgba(0,0,0,0.8)',
                opacity: imageLoaded ? 1 : 0,
                transition: 'opacity 0.2s ease',
              }}
            />
          )}
        </div>

        {/* Metadata Line Below Image */}
        <div
          style={{
            width: '100%',
            marginTop: '16px',
            paddingTop: '12px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.78rem',
            color: '#94a3b8',
            flexWrap: 'wrap',
          }}
        >
          <span>Resolution: {scene?.resolution || (bandUpper === 'VV' || bandUpper === 'VH' ? '10 m' : '30 m')}</span>
          <span>•</span>
          <span>CRS: {scene?.crs || (bandUpper === 'VV' || bandUpper === 'VH' ? 'EPSG:4326' : 'EPSG:32645')}</span>
          {scene?.path_row_formatted && (
            <>
              <span>•</span>
              <span>Path/Row: {scene.path_row_formatted}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
