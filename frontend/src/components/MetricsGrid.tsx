import React from 'react';
import { Activity, Droplets, TreeDeciduous, Radio, TrendingUp, TrendingDown, Percent } from 'lucide-react';
import type { QueryResult } from '../types';

interface MetricsGridProps {
  result: QueryResult | null;
}

const formatNum = (val: any, decimals: number = 2, prefixPlus: boolean = false): string => {
  if (val === null || val === undefined) return '--';
  const num = typeof val === 'number' ? val : parseFloat(val);
  if (isNaN(num)) return String(val);
  const formatted = num.toFixed(decimals);
  return prefixPlus && num > 0 ? `+${formatted}` : formatted;
};

export const MetricsGrid: React.FC<MetricsGridProps> = ({ result }) => {
  if (!result || !result.analysis) return null;

  const analysis = result.analysis;
  const cards: { label: string; value: string; sub?: string; icon: React.ReactNode; color?: string }[] = [];

  // NDVI stats
  const ndviStats = analysis.ndvi_statistics || (result.selected_tool !== 'change_detection_model' ? analysis.statistics : null);
  if (ndviStats && (ndviStats.mean_ndvi !== undefined || ndviStats.mean !== undefined)) {
    const m = ndviStats.mean_ndvi !== undefined ? ndviStats.mean_ndvi : ndviStats.mean;
    cards.push({
      label: 'Mean NDVI Canopy',
      value: formatNum(m, 3, true),
      sub: ndviStats.stddev !== undefined ? `StdDev: ±${formatNum(ndviStats.stddev, 3)}` : 'Surface Reflectance',
      icon: <TreeDeciduous size={18} color="#34d399" />,
      color: '#34d399',
    });
  }

  // Spectral indices
  if (analysis.spectral_indices) {
    const indices = analysis.spectral_indices;
    if (indices.mean_ndwi !== undefined) {
      cards.push({
        label: 'NDWI (McFeeters 1996)',
        value: formatNum(indices.mean_ndwi, 3, true),
        sub: 'Open Water Delineation',
        icon: <Droplets size={18} color="#38bdf8" />,
        color: '#38bdf8',
      });
    }
    if (indices.simple_ratio !== undefined) {
      cards.push({
        label: 'Simple Biomass Ratio',
        value: formatNum(indices.simple_ratio, 2),
        sub: 'NIR (B5) / Red (B4)',
        icon: <Activity size={18} color="#f59e0b" />,
        color: '#f59e0b',
      });
    }
  }

  // Change detection metrics
  if (analysis.statistics && (
    analysis.statistics.vegetation_gain_percentage !== undefined ||
    analysis.statistics.increase_percentage !== undefined ||
    analysis.statistics.mean_delta_ndvi !== undefined ||
    analysis.statistics.mean_ndvi_change !== undefined
  )) {
    const s = analysis.statistics;
    const bMean = s.baseline_mean_ndvi ?? s.before_mean_ndvi ?? s.before_mean;
    const aMean = s.monitoring_mean_ndvi ?? s.after_mean_ndvi ?? s.after_mean;
    const dMean = s.mean_delta_ndvi ?? s.delta_mean_ndvi ?? s.mean_ndvi_change;
    const gainPct = s.vegetation_gain_percentage ?? s.increase_percentage;
    const lossPct = s.vegetation_loss_percentage ?? s.decrease_percentage;
    const stablePct = s.stable_percentage ?? s.stable_pct;

    if (bMean !== undefined) {
      cards.push({
        label: 'Baseline Mean NDVI (T1)',
        value: formatNum(bMean, 4),
        sub: 'Initial Vegetation Baseline',
        icon: <TreeDeciduous size={18} color="#38bdf8" />,
        color: '#38bdf8',
      });
    }
    if (aMean !== undefined) {
      cards.push({
        label: 'Monitoring Mean NDVI (T2)',
        value: formatNum(aMean, 4),
        sub: 'Monitoring Pass Status',
        icon: <TreeDeciduous size={18} color="#34d399" />,
        color: '#34d399',
      });
    }
    if (dMean !== undefined) {
      cards.push({
        label: 'Net Delta (ΔNDVI)',
        value: formatNum(dMean, 4, true),
        sub: 'Temporal Shift (T2 - T1)',
        icon: <Activity size={18} color="#38bdf8" />,
        color: '#38bdf8',
      });
    }
    if (gainPct !== undefined) {
      cards.push({
        label: 'Vegetation Gain',
        value: `${formatNum(gainPct, 1)}%`,
        sub: 'Green Pixels (Greening)',
        icon: <TrendingUp size={18} color="#10b981" />,
        color: '#10b981',
      });
    }
    if (lossPct !== undefined) {
      cards.push({
        label: 'Vegetation Loss',
        value: `${formatNum(lossPct, 1)}%`,
        sub: 'Red Pixels (Degradation)',
        icon: <TrendingDown size={18} color="#f43f5e" />,
        color: '#f43f5e',
      });
    }
    if (stablePct !== undefined) {
      cards.push({
        label: 'Stable Landscape',
        value: `${formatNum(stablePct, 1)}%`,
        sub: 'Gray Pixels (Controlled)',
        icon: <Percent size={18} color="#94a3b8" />,
        color: '#94a3b8',
      });
    }
  }

  // SAR metrics
  if (analysis.sar_metrics) {
    const sar = analysis.sar_metrics;
    if (sar.mean_sigma0_vv_db !== undefined) {
      cards.push({
        label: 'SAR VV Backscatter',
        value: `${formatNum(sar.mean_sigma0_vv_db, 2)} dB`,
        sub: 'Surface Roughness Signal',
        icon: <Radio size={18} color="#a855f7" />,
        color: '#a855f7',
      });
    }
    if (sar.mean_sigma0_vh_db !== undefined) {
      cards.push({
        label: 'SAR VH Cross-Pol',
        value: `${formatNum(sar.mean_sigma0_vh_db, 2)} dB`,
        sub: 'Volume Scattering Signal',
        icon: <Radio size={18} color="#c084fc" />,
        color: '#c084fc',
      });
    }
    if (sar.mean_rvi !== undefined) {
      cards.push({
        label: 'Radar Veg Index (RVI)',
        value: formatNum(sar.mean_rvi, 3),
        sub: 'Polarimetric Canopy Structure',
        icon: <TreeDeciduous size={18} color="#a855f7" />,
        color: '#a855f7',
      });
    }
  }

  // Cross-sensor consensus
  if (analysis.fusion_metrics && analysis.fusion_metrics.dual_sensor_vegetation_agreement_percentage !== undefined) {
    cards.push({
      label: 'Cross-Sensor Agreement',
      value: `${formatNum(analysis.fusion_metrics.dual_sensor_vegetation_agreement_percentage, 1)}%`,
      sub: 'Optical NDVI ∩ SAR RVI',
      icon: <Activity size={18} color="#38bdf8" />,
      color: '#38bdf8',
    });
  }

  if (cards.length === 0) return null;

  return (
    <div className="metrics-section">
      {cards.map((c, i) => (
        <div key={i} className="metric-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="metric-label">{c.label}</span>
            {c.icon}
          </div>
          <span className="metric-value" style={{ color: c.color || '#38bdf8' }}>
            {c.value}
          </span>
          {c.sub && <span className="metric-sub">{c.sub}</span>}
        </div>
      ))}
    </div>
  );
};
