import React from 'react';
import {
  Satellite,
  ArrowRight,
  ChevronDown,
  Layers,
  BarChart2,
  Cpu,
  ShieldCheck,
  Eye,
  Terminal,
  FileCheck2,
  CheckCircle2,
  Search
} from 'lucide-react';
import { CircularCapabilityCarousel } from '../components/CircularCapabilityCarousel';
import { HeroOrbitalVisual } from '../components/HeroOrbitalVisual';

interface LandingPageProps {
  onLaunchDashboard: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onLaunchDashboard }) => {
  React.useEffect(() => {
    // Proactively ping health endpoint to trigger Render wake-up while judge explores the landing page
    fetch('/api/health', {
      headers: { 'Cache-Control': 'no-cache' },
    }).catch(() => {});
  }, []);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="landing-container">
      {/* 1. TOP AEROSPACE NAVIGATION */}
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-brand">
            <div className="landing-brand-icon">
              <Satellite size={22} color="#38bdf8" />
            </div>
            <div className="landing-brand-text">
              <span className="landing-brand-title">SATQUERY AI</span>
              <span className="landing-brand-subtitle">SIH 2026</span>
            </div>
          </div>

          <div className="landing-nav-links">
            <button onClick={() => scrollToSection('about')} className="landing-nav-link">About</button>
            <button onClick={() => scrollToSection('capabilities')} className="landing-nav-link">Capabilities</button>
            <button onClick={() => scrollToSection('how-it-works')} className="landing-nav-link">How It Works</button>
            <button onClick={() => scrollToSection('foundation')} className="landing-nav-link">Scientific Foundation</button>
          </div>

          <div className="landing-nav-actions">
            <button onClick={onLaunchDashboard} className="landing-cta-btn compact">
              <span>Launch Dashboard</span>
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </nav>

      {/* 2. HERO SECTION */}
      <header className="landing-hero">
        <div className="landing-hero-bg-grid" />
        <div className="landing-hero-glow" />

        <div className="landing-hero-content">
          {/* Left Column: Mission Description */}
          <div className="landing-hero-text">
            <div className="landing-hero-badge">
              <ShieldCheck size={14} color="#34d399" />
              <span>SIH 2026 • AUTONOMOUS MULTIMODAL REMOTE SENSING AI</span>
            </div>

            <h1 className="landing-hero-title">
              SATQUERY AI
            </h1>

            <h2 className="landing-hero-subtitle">
              Autonomous Multimodal Remote Sensing Assistant
            </h2>

            <p className="landing-hero-description">
              Ask questions about satellite imagery in natural language. SatQuery AI combines remote-sensing science, multimodal AI and agentic analysis to turn complex satellite data into explainable insights.
            </p>

            <div className="landing-hero-cta-group">
              <button onClick={onLaunchDashboard} className="landing-cta-btn primary">
                <span>GET STARTED</span>
                <ArrowRight size={17} />
              </button>

              <button onClick={() => scrollToSection('capabilities')} className="landing-cta-btn secondary">
                <span>EXPLORE CAPABILITIES</span>
                <ChevronDown size={17} />
              </button>
            </div>

            {/* 5. Compact Technology Status Bar */}
            <div className="landing-tech-bar">
              <span className="landing-tech-chip">
                <span className="dot dot-cyan" /> Remote Sensing AI
              </span>
              <span className="landing-tech-chip">
                <span className="dot dot-purple" /> SmolVLM + RS LoRA
              </span>
              <span className="landing-tech-chip">
                <span className="dot dot-emerald" /> Multispectral Analysis
              </span>
              <span className="landing-tech-chip">
                <span className="dot dot-amber" /> Optical + SAR
              </span>
              <span className="landing-tech-chip">
                <span className="dot dot-blue" /> FastAPI + React
              </span>
              <span className="landing-tech-chip">
                <span className="dot dot-emerald" /> SIH 2026
              </span>
            </div>
          </div>

          {/* Right Column: Dynamic Hero Orbital Visual (Continuous Orbit, Scanning Swath, Floating Cards) */}
          <HeroOrbitalVisual />
        </div>

      </header>

      {/* 6. "WHAT IS SATQUERY AI?" SECTION */}
      <section id="about" className="landing-section">
        <div className="landing-section-header">
          <span className="section-eyebrow">SYSTEM OVERVIEW</span>
          <h2 className="section-title">WHAT IS SATQUERY AI?</h2>
          <p className="section-summary">
            SatQuery AI provides a natural-language interface for remote-sensing imagery. Instead of manually selecting bands, algorithms and GIS tools, users can ask a question and the system determines the appropriate analysis.
          </p>
        </div>

        {/* Clean Process Pipeline Visual */}
        <div className="pipeline-flow-container">
          <div className="pipeline-flow-step">
            <div className="pipeline-step-node">
              <Search size={18} color="#38bdf8" />
            </div>
            <span className="pipeline-step-title">USER QUESTION</span>
            <span className="pipeline-step-sub">Natural-Language Intent</span>
          </div>

          <div className="pipeline-connector-arrow">→</div>

          <div className="pipeline-flow-step">
            <div className="pipeline-step-node">
              <Terminal size={18} color="#34d399" />
            </div>
            <span className="pipeline-step-title">AI AGENT</span>
            <span className="pipeline-step-sub">Dynamic Routing & Verification</span>
          </div>

          <div className="pipeline-connector-arrow">→</div>

          <div className="pipeline-flow-step">
            <div className="pipeline-step-node">
              <BarChart2 size={18} color="#10b981" />
            </div>
            <span className="pipeline-step-title">SCIENTIFIC TOOLS</span>
            <span className="pipeline-step-sub">Deterministic Physical Math</span>
          </div>

          <div className="pipeline-connector-arrow">→</div>

          <div className="pipeline-flow-step">
            <div className="pipeline-step-node">
              <Eye size={18} color="#a855f7" />
            </div>
            <span className="pipeline-step-title">REMOTE-SENSING MODELS</span>
            <span className="pipeline-step-sub">SmolVLM-500M + RS LoRA</span>
          </div>

          <div className="pipeline-connector-arrow">→</div>

          <div className="pipeline-flow-step">
            <div className="pipeline-step-node">
              <Layers size={18} color="#38bdf8" />
            </div>
            <span className="pipeline-step-title">VISUAL EVIDENCE</span>
            <span className="pipeline-step-sub">Rasters, Triplet, Composites</span>
          </div>

          <div className="pipeline-connector-arrow">→</div>

          <div className="pipeline-flow-step">
            <div className="pipeline-step-node">
              <FileCheck2 size={18} color="#10b981" />
            </div>
            <span className="pipeline-step-title">EXPLAINABLE ANSWER</span>
            <span className="pipeline-step-sub">Audited Execution Trace</span>
          </div>
        </div>
      </section>

      {/* 7. CORE CAPABILITIES (Interactive 3D Orbital Carousel with Card Flip) */}
      <section id="capabilities" className="landing-section dark-alt">
        <div className="landing-section-header">
          <span className="section-eyebrow">CORE CAPABILITIES</span>
          <h2 className="section-title">5 Autonomous Scientific Workflows</h2>
          <p className="section-summary">
            Explore our multimodal remote-sensing capabilities in a dynamic orbital circle. Drag horizontally with your mouse to rotate the cylinder, and click any card to flip and inspect its scientific formulas and sensor specifications.
          </p>
        </div>

        <CircularCapabilityCarousel />
      </section>

      {/* 8. "HOW IT WORKS" SECTION */}
      <section id="how-it-works" className="landing-section">
        <div className="landing-section-header">
          <span className="section-eyebrow">WORKFLOW ORCHESTRATION</span>
          <h2 className="section-title">HOW IT WORKS</h2>
          <p className="section-summary">
            A 5-step autonomous cycle resolving questions from intent to auditable verification.
          </p>
        </div>

        <div className="workflow-steps-container">
          {/* Step 1 */}
          <div className="workflow-step-card">
            <div className="workflow-step-num">01</div>
            <h4 className="workflow-step-title">ASK</h4>
            <p className="workflow-step-desc">
              Ask a question in natural language.
            </p>
          </div>

          <div className="workflow-divider-arrow">↓</div>

          {/* Step 2 */}
          <div className="workflow-step-card">
            <div className="workflow-step-num">02</div>
            <h4 className="workflow-step-title">UNDERSTAND</h4>
            <p className="workflow-step-desc">
              SatQuery identifies the scientific intent and required inputs.
            </p>
          </div>

          <div className="workflow-divider-arrow">↓</div>

          {/* Step 3 */}
          <div className="workflow-step-card">
            <div className="workflow-step-num">03</div>
            <h4 className="workflow-step-title">ANALYZE</h4>
            <p className="workflow-step-desc">
              Deterministic remote-sensing tools perform the calculations.
            </p>
          </div>

          <div className="workflow-divider-arrow">↓</div>

          {/* Step 4 */}
          <div className="workflow-step-card">
            <div className="workflow-step-num">04</div>
            <h4 className="workflow-step-title">INTERPRET</h4>
            <p className="workflow-step-desc">
              SmolVLM + RS LoRA provides visual interpretation.
            </p>
          </div>

          <div className="workflow-divider-arrow">↓</div>

          {/* Step 5 */}
          <div className="workflow-step-card">
            <div className="workflow-step-num">05</div>
            <h4 className="workflow-step-title">EXPLAIN</h4>
            <p className="workflow-step-desc">
              Receive evidence, measurements and an auditable execution trace.
            </p>
          </div>
        </div>
      </section>

      {/* 9. SCIENTIFIC FOUNDATION */}
      <section id="foundation" className="landing-section dark-alt">
        <div className="landing-section-header">
          <span className="section-eyebrow">SYSTEM ARCHITECTURE</span>
          <h2 className="section-title">Scientific Foundation</h2>
          <p className="section-summary">
            Ground-truth technologies, mathematical indices, and multimodal model weights active in SatQuery.
          </p>
        </div>

        <div className="foundation-grid">
          {/* Pillar 1 */}
          <div className="foundation-card">
            <div className="foundation-header">
              <Satellite size={20} color="#38bdf8" />
              <h3>REMOTE SENSING</h3>
            </div>
            <ul className="foundation-list">
              <li><strong>Landsat-8 & Landsat-9:</strong> Operational Land Imager 2 (30m UTM)</li>
              <li><strong>Sentinel-1A SAR:</strong> C-band Synthetic Aperture Radar (10m)</li>
              <li><strong>Multispectral Bands:</strong> Blue (B2), Green (B3), Red (B4), NIR (B5)</li>
              <li><strong>GeoTIFF Rasters:</strong> Calibrated surface reflectance tensors</li>
            </ul>
          </div>

          {/* Pillar 2 */}
          <div className="foundation-card">
            <div className="foundation-header">
              <Cpu size={20} color="#a855f7" />
              <h3>AI & MULTIMODAL</h3>
            </div>
            <ul className="foundation-list">
              <li><strong>SmolVLM-500M:</strong> Compact Vision-Language Model</li>
              <li><strong>RS LoRA:</strong> Low-Rank Adaptation for Remote Sensing</li>
              <li><strong>Vision-Language Synthesis:</strong> Scene description & QA</li>
              <li><strong>FP16 GPU Inference:</strong> Hardware-accelerated execution</li>
            </ul>
          </div>

          {/* Pillar 3 */}
          <div className="foundation-card">
            <div className="foundation-header">
              <BarChart2 size={20} color="#10b981" />
              <h3>SCIENTIFIC ANALYSIS</h3>
            </div>
            <ul className="foundation-list">
              <li><strong>NDVI:</strong> Normalized Difference Vegetation Index (Rouse 1974)</li>
              <li><strong>NDWI:</strong> Normalized Difference Water Index (McFeeters 1996)</li>
              <li><strong>Spectral Analysis:</strong> 4-Band surface reflectance profiles</li>
              <li><strong>Change Detection:</strong> Bi-temporal NDVI differencing</li>
              <li><strong>SAR Fusion:</strong> Dual-polarization VV/VH backscatter & RVI</li>
            </ul>
          </div>

          {/* Pillar 4 */}
          <div className="foundation-card">
            <div className="foundation-header">
              <Terminal size={20} color="#f59e0b" />
              <h3>AGENTIC ORCHESTRATION</h3>
            </div>
            <ul className="foundation-list">
              <li><strong>Intent Detection:</strong> Zero-shot query classification</li>
              <li><strong>Tool Selection:</strong> Rule-based scientific routing</li>
              <li><strong>Compatibility Validation:</strong> Path/Row and CRS checks</li>
              <li><strong>Execution Trace:</strong> Step-by-step latency & ISO timestamps</li>
            </ul>
          </div>
        </div>
      </section>

      {/* 10. SIH SECTION */}
      <section className="landing-section">
        <div className="sih-banner-card">
          <div className="sih-badge-pill">
            <ShieldCheck size={16} />
            <span>SIH 2026 • REMOTE SENSING AI</span>
          </div>

          <h2 className="sih-banner-title">BUILT FOR SMART INDIA HACKATHON 2026</h2>

          <p className="sih-banner-desc">
            SatQuery AI is designed as an agentic multimodal remote-sensing system for natural-language interaction with satellite imagery.
          </p>

          <div className="sih-features-row">
            <div className="sih-feature-item">
              <CheckCircle2 size={16} color="#34d399" />
              <span>Real Landsat & Sentinel-1 Data</span>
            </div>
            <div className="sih-feature-item">
              <CheckCircle2 size={16} color="#34d399" />
              <span>Deterministic Scientific Rigor</span>
            </div>
            <div className="sih-feature-item">
              <CheckCircle2 size={16} color="#34d399" />
              <span>Auditable Heuristic Confidence</span>
            </div>
          </div>
        </div>
      </section>

      {/* 11. FINAL CALL TO ACTION */}
      <section className="landing-cta-section">
        <div className="landing-cta-content">
          <h2 className="landing-cta-title">Ready to explore satellite intelligence?</h2>
          <p className="landing-cta-desc">
            Experience autonomous remote-sensing vision-language analysis on real multi-sensor satellite imagery.
          </p>
          <button onClick={onLaunchDashboard} className="landing-cta-btn primary large">
            <span>LAUNCH SATQUERY AI</span>
            <ArrowRight size={18} />
          </button>
        </div>
      </section>

      {/* 12. FOOTER */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="landing-footer-brand">
            <div className="landing-brand">
              <div className="landing-brand-icon">
                <Satellite size={20} color="#38bdf8" />
              </div>
              <div className="landing-brand-text">
                <span className="landing-brand-title">SATQUERY AI</span>
                <span className="landing-brand-subtitle">Autonomous Multimodal Remote Sensing Assistant</span>
              </div>
            </div>
            <p className="footer-copyright-text">
              Smart India Hackathon (SIH 2026) Project. All remote sensing computations are physically calibrated.
            </p>
          </div>

          <div className="landing-footer-links">
            <button onClick={onLaunchDashboard} className="footer-link-btn">Launch Dashboard</button>
            <button onClick={() => scrollToSection('capabilities')} className="footer-link-btn">Capabilities</button>
            <button onClick={() => scrollToSection('how-it-works')} className="footer-link-btn">How It Works</button>
            <button onClick={() => scrollToSection('foundation')} className="footer-link-btn">Scientific Foundation</button>
          </div>
        </div>
      </footer>
    </div>
  );
};
