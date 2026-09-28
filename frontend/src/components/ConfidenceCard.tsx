import React from 'react';
import { ShieldCheck, CheckCircle2 } from 'lucide-react';
import type { ConfidenceInfo } from '../types';

interface ConfidenceCardProps {
  confidence?: ConfidenceInfo;
}

export const ConfidenceCard: React.FC<ConfidenceCardProps> = ({ confidence }) => {
  if (!confidence) return null;

  const scorePct = Math.round(confidence.score * 100);
  const level = (confidence.level || 'high').toUpperCase();

  const getLevelColor = (lvl: string) => {
    switch (lvl) {
      case 'HIGH': return '#34d399';
      case 'MEDIUM': return '#fbbf24';
      default: return '#fb7185';
    }
  };

  return (
    <div className="confidence-card">
      <div className="confidence-header">
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontFamily: 'var(--font-display)' }}>
          <ShieldCheck size={18} color={getLevelColor(level)} />
          Estimated Confidence
        </span>
        <span
          style={{
            fontSize: '0.68rem',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: 4,
            background: `${getLevelColor(level)}15`,
            border: `1px solid ${getLevelColor(level)}40`,
            color: getLevelColor(level),
          }}
        >
          {level} CONFIDENCE
        </span>
      </div>

      {/* Scientific Explanation Subtitle */}
      <p className="confidence-sub-explanation">
        Estimated from deterministic calculations, generated evidence, spatial consistency and successful model synthesis.
      </p>

      <div className="confidence-score-display">
        <span className="confidence-number" style={{ color: getLevelColor(level) }}>
          {scorePct}%
        </span>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: '0.8rem', color: '#f8fafc', fontWeight: 600 }}>Scientific Evidence Score</span>
          <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Heuristic Decision Bounds (0.0 – 1.0)</span>
        </div>
      </div>

      <div className="confidence-meter">
        <div
          className="confidence-fill"
          style={{
            width: `${scorePct}%`,
            background: `linear-gradient(90deg, #10b981, ${getLevelColor(level)})`,
          }}
        />
      </div>

      {confidence.basis && confidence.basis.length > 0 && (
        <div style={{ marginTop: 6 }}>
          <span style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
            Audit & Decision Grounds:
          </span>
          <ul className="confidence-reasons-list">
            {confidence.basis.map((reason, idx) => (
              <li key={idx} className="confidence-reason-item">
                <CheckCircle2 size={13} color="#34d399" style={{ flexShrink: 0, marginTop: 2 }} />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
