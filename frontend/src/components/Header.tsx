import React from 'react';
import { Satellite, Cpu, ShieldCheck, Home, Loader2, RefreshCw } from 'lucide-react';

export type BackendHealthStatus = 'disconnected' | 'waking' | 'online' | 'unavailable';

interface HeaderProps {
  backendOnline: boolean;
  backendStatus?: BackendHealthStatus;
  onRetry?: () => void;
  onGoHome?: () => void;
  vlmEnabled?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  backendOnline,
  backendStatus,
  onRetry,
  onGoHome,
  vlmEnabled,
}) => {
  // Determine effective status: prioritize backendStatus if provided
  const currentStatus: BackendHealthStatus = backendStatus || (backendOnline ? 'online' : 'disconnected');

  // Determine if running in cloud low-memory deployment (Render) vs local GPU environment
  const isCloudDeployment = vlmEnabled !== undefined
    ? !vlmEnabled
    : (typeof window !== 'undefined' && (window.location.hostname.includes('render.com') || window.location.hostname.includes('onrender.com')));

  const vlmRuntimeLabel = isCloudDeployment
    ? 'SmolVLM-500M + RS LoRA · Cloud VLM Bypassed'
    : 'SmolVLM-500M + RS LoRA · NVIDIA GTX 1650 FP16';

  const renderStatusBadge = () => {
    if (currentStatus === 'online') {
      return (
        <div className="status-badge online" title="FastAPI Remote-Sensing Backend is connected and operational">
          <div className="status-dot" style={{ backgroundColor: '#10b981', boxShadow: '0 0 10px #10b981' }} />
          <span>FastAPI Backend Online</span>
        </div>
      );
    }

    if (currentStatus === 'waking') {
      return (
        <div className="status-badge waking" title="Backend is waking up from idle state. Automatic retry in progress...">
          <div className="status-dot waking" style={{ backgroundColor: '#f59e0b', boxShadow: '0 0 10px #f59e0b' }} />
          <Loader2 size={12} className="status-spin" style={{ color: '#f59e0b' }} />
          <span>Waking backend...</span>
        </div>
      );
    }

    // Unavailable or Disconnected
    return (
      <div className="status-badge disconnected" title="Backend is currently offline or unreachable">
        <div className="status-dot" style={{ backgroundColor: '#f43f5e', boxShadow: '0 0 10px #f43f5e' }} />
        <span>Backend Disconnected</span>
        {onRetry && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRetry();
            }}
            className="badge-retry-btn"
            title="Retry connecting to backend"
          >
            <RefreshCw size={10} />
            <span>Retry</span>
          </button>
        )}
      </div>
    );
  };

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

        {renderStatusBadge()}

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
