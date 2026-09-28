import React, { useState } from 'react';
import { GitCommit, Clock, ChevronDown, ChevronUp, Code2, CheckCircle2, ChevronRight, Layers, Terminal, Wrench, Eye, AlertCircle } from 'lucide-react';
import type { ExecutionTrace as TraceType } from '../types';

interface ExecutionTraceProps {
  trace?: TraceType;
}

export const ExecutionTrace: React.FC<ExecutionTraceProps> = ({ trace }) => {
  const [showJson, setShowJson] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({});

  if (!trace || !trace.steps || trace.steps.length === 0) return null;

  const toggleStep = (index: number) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  const getStepIcon = (stepName: string) => {
    switch (stepName.toLowerCase()) {
      case 'input_analysis': return <Layers size={14} color="#38bdf8" />;
      case 'query_parsing': return <Terminal size={14} color="#34d399" />;
      case 'multi_intent_detection': return <Terminal size={14} color="#38bdf8" />;
      case 'active_input_validation': return <CheckCircle2 size={14} color="#38bdf8" />;
      case 'tool_selection': return <Wrench size={14} color="#f59e0b" />;
      case 'tool_execution': return <CheckCircle2 size={14} color="#10b981" />;
      case 'tool_blocked': return <AlertCircle size={14} color="#f59e0b" />;
      case 'result_fusion': return <CheckCircle2 size={14} color="#10b981" />;
      case 'vlm_hybrid_synthesis':
      case 'change_vqa_synthesis':
      case 'fusion_vlm_synthesis': return <Eye size={14} color="#a855f7" />;
      default: return <GitCommit size={14} color="#38bdf8" />;
    }
  };

  const formatStepTitle = (stepName: string) => {
    switch (stepName) {
      case 'input_analysis': return 'Input Scene & Raster Analysis';
      case 'query_parsing': return 'Natural Query Intent Detection';
      case 'multi_intent_detection': return 'Multi-Intent Query Decomposition';
      case 'active_input_validation': return 'Active Input Validation';
      case 'tool_selection': return 'Tool Selection & Data Compatibility';
      case 'tool_execution': return 'Deterministic Scientific Calculation';
      case 'tool_blocked': return 'Component Notice (Prerequisite Check)';
      case 'result_fusion': return 'Multi-Tool Result Fusion & Synthesis';
      case 'vlm_hybrid_synthesis': return 'SmolVLM Multimodal Hybrid Synthesis';
      case 'change_vqa_synthesis': return 'VLM-Assisted Change Interpretation';
      case 'fusion_vlm_synthesis': return 'Optical + SAR Cross-Sensor Synthesis';
      case 'result_interpretation': return 'Scientific Synthesis & Estimated Confidence';
      default: return stepName.replace(/_/g, ' ').toUpperCase();
    }
  };

  return (
    <div className="trace-card">
      <div className="trace-title-row">
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'var(--font-display)', fontSize: '0.95rem', fontWeight: 600 }}>
          <GitCommit size={16} color="#38bdf8" />
          Auditable Execution Trace
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {trace.total_execution_time_seconds !== undefined && (
            <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 4 }}>
              <Clock size={13} />
              Latency: <strong style={{ color: '#f8fafc' }}>{trace.total_execution_time_seconds}s</strong>
            </span>
          )}
          <button
            onClick={() => setShowJson(!showJson)}
            style={{
              background: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: 4,
              padding: '3px 8px',
              color: '#38bdf8',
              fontSize: '0.72rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <Code2 size={12} />
            {showJson ? 'Hide Raw JSON' : 'Inspect Raw JSON'}
            {showJson ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>
      </div>

      {showJson ? (
        <pre
          style={{
            background: '#020617',
            padding: 14,
            borderRadius: 6,
            border: '1px solid #1e293b',
            color: '#38bdf8',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.72rem',
            overflowX: 'auto',
            maxHeight: 320,
          }}
        >
          {JSON.stringify(trace, null, 2)}
        </pre>
      ) : (
        <div className="trace-timeline-expandable">
          {trace.steps.map((step, idx) => {
            const isExpanded = !!expandedSteps[idx];
            const hasDetails = step.details && Object.keys(step.details).length > 0;

            return (
              <div key={idx} className={`trace-step-row ${step.status}`}>
                <div
                  className="step-header-clickable"
                  onClick={() => hasDetails && toggleStep(idx)}
                  style={{ cursor: hasDetails ? 'pointer' : 'default' }}
                >
                  <div className="step-icon-box">
                    {getStepIcon(step.step)}
                  </div>

                  <div className="step-main-meta">
                    <span className="step-title-text">{formatStepTitle(step.step)}</span>
                    <span className={`step-status-tag ${step.status}`}>{step.status}</span>
                  </div>

                  <span className="step-timestamp-text">
                    {step.timestamp ? step.timestamp.slice(11, 19) : `Step ${idx + 1}`}
                  </span>

                  {hasDetails && (
                    <span className="step-expand-icon">
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronRight size={14} />}
                    </span>
                  )}
                </div>

                {/* 6. Expandable Step Details */}
                {isExpanded && step.details && (
                  <div className="step-details-container">
                    <div className="details-grid">
                      {Object.entries(step.details).map(([key, val]) => (
                        <div key={key} className="detail-field">
                          <span className="detail-key">{key.replace(/_/g, ' ')}:</span>
                          {key === 'selected_scene' || key === 'target_scene_id' ? (
                            <span className="detail-val font-semibold text-cyan-300 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/30">
                              {String(val)}
                            </span>
                          ) : (
                            <span className="detail-val">
                              {typeof val === 'object' && val !== null
                                ? JSON.stringify(val)
                                : String(val)}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
