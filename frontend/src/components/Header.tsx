import React from 'react';
import { Satellite, Cpu, ShieldCheck, Home } from 'lucide-react';

interface HeaderProps {
  backendOnline: boolean;
  onGoHome?: () => void;
  vlmEnabled?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ backendOnline, onGoHome, vlmEnabled }) => {
  // Determine if running in cloud low-memory deployment (Render) vs local GPU environment
  const isCloudDeployment = vlmEnabled !== undefined
    ? !vlmEnabled
    : (typeof window !== 'undefined' && (window.location.hostname.includes('render.com') || window.location.hostname.includes('onrender.com')));

  const vlmRuntimeLabel = isCloudDeployment
    ? 'SmolVLM-500M + RS LoRA · Cloud VLM Bypassed'
    : 'SmolVLM-500M + RS LoRA · NVIDIA GTX 1650 FP16';

  return (
    <header className="mission-header">
      <div
        className="header-brand"
        onClick={onGoHome}
        style={{ cursor: onGoHome ? 'pointer' : 'default' }}
        title={onGoHome ? 'Return to Welcome Page' : undefined}
      >
        <div className="brand-icon-wrapper">
          <Satellite size={24} />
        </div>
        <div className="brand-titles">
          <h1>SatQuery AI</h1>
          <p>Autonomous Multimodal Remote Sensing Assistant</p>
        </div>
      </div>

      <div className="header-badges">
        {onGoHome && (
          <button
            onClick={onGoHome}
            className="home-nav-pill-btn"
            title="Return to Welcome Page"
          >
            <Home size={13} />
            <span>Welcome Page</span>
          </button>
        )}
        <div className={`status-badge ${backendOnline ? 'online' : ''}`}>
          <div className="status-dot" style={{ backgroundColor: backendOnline ? '#10b981' : '#f43f5e' }} />
          <span>{backendOnline ? 'FastAPI Backend Online' : 'Backend Disconnected'}</span>
        </div>

        <div className="status-badge" title={isCloudDeployment ? "Cloud low-memory deployment (VLM bypassed, raster tools active)" : "Local hardware acceleration (GTX 1650 FP16)"}>
          <Cpu size={14} color={isCloudDeployment ? "#f59e0b" : "#a855f7"} />
          <span>{vlmRuntimeLabel}</span>
        </div>

        <div className="sih-badge">
          <ShieldCheck size={14} style={{ display: 'inline', marginRight: 4, verticalAlign: 'text-bottom' }} />
          SIH 2026 AUDITED
        </div>
      </div>
    </header>
  );
};
