import React, { useEffect, useRef, useState } from 'react';
import { Satellite, Layers, Cpu } from 'lucide-react';

export const HeroOrbitalVisual: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const satelliteGroupRef = useRef<SVGGElement>(null);
  const beamPolygonRef = useRef<SVGPolygonElement>(null);
  const footprintGroupRef = useRef<SVGGElement>(null);
  const dataStreamPathRef = useRef<SVGPathElement>(null);
  const dataPacketRef = useRef<SVGCircleElement>(null);

  const [parallax, setParallax] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(false);

  const animFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(performance.now());

  // Check for reduced motion preference
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      setPrefersReducedMotion(mediaQuery.matches);
      const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
      mediaQuery.addEventListener('change', handler);
      return () => mediaQuery.removeEventListener('change', handler);
    }
  }, []);

  // Continuous Orbital Physics Loop
  useEffect(() => {
    if (prefersReducedMotion) return;

    // Orbit parameters
    const cx = 250;
    const cy = 250;
    const rx = 205;
    const ry = 98;
    const phi = -22 * (Math.PI / 180); // tilt angle in radians
    const cosPhi = Math.cos(phi);
    const sinPhi = Math.sin(phi);
    const ORBIT_DURATION_SEC = 15; // 15 seconds per orbit

    const loop = (now: number) => {
      const elapsed = (now - startTimeRef.current) / 1000;
      const progress = (elapsed % ORBIT_DURATION_SEC) / ORBIT_DURATION_SEC;
      const theta = progress * 2 * Math.PI;

      // Elliptical point before rotation
      const u = rx * Math.cos(theta);
      const v = ry * Math.sin(theta);

      // Rotated orbital point
      const x = cx + u * cosPhi - v * sinPhi;
      const y = cy + u * sinPhi + v * cosPhi;

      // Tangent vector for natural flight orientation
      const du = -rx * Math.sin(theta);
      const dv = ry * Math.cos(theta);
      const dx = du * cosPhi - dv * sinPhi;
      const dy = du * sinPhi + dv * cosPhi;
      const headingDeg = (Math.atan2(dy, dx) * 180) / Math.PI;

      // When v > 0, satellite is in front of Earth (closest to camera); when v < 0, it orbits behind
      const isFront = v > -10;
      const depthFactor = (v + ry) / (2 * ry); // 0.0 (far behind) to 1.0 (front center)
      const satScale = 0.85 + depthFactor * 0.35;
      const satOpacity = 0.5 + depthFactor * 0.5;

      // Update Satellite Position and Angle
      if (satelliteGroupRef.current) {
        satelliteGroupRef.current.setAttribute(
          'transform',
          `translate(${x.toFixed(2)}, ${y.toFixed(2)}) rotate(${headingDeg.toFixed(1)}) scale(${satScale.toFixed(2)})`
        );
        satelliteGroupRef.current.style.opacity = satOpacity.toFixed(2);
      }

      // Calculate Footprint Position on Earth surface
      // Footprint tracks along the Earth globe with a gentle projection
      const fx = cx + 0.38 * (x - cx);
      const fy = cy + 0.38 * (y - cy) + 12;

      // Width of beam footprint on Earth
      const fWidth = 24 * satScale;

      // Update Scanning Beam Polygon (from Satellite lens to Earth Footprint)
      if (beamPolygonRef.current) {
        if (isFront) {
          const p1x = x.toFixed(1);
          const p1y = y.toFixed(1);
          const p2x = (fx - fWidth).toFixed(1);
          const p2y = fy.toFixed(1);
          const p3x = (fx + fWidth).toFixed(1);
          const p3y = fy.toFixed(1);
          beamPolygonRef.current.setAttribute('points', `${p1x},${p1y} ${p2x},${p2y} ${p3x},${p3y}`);
          beamPolygonRef.current.style.opacity = (0.2 + depthFactor * 0.25).toFixed(2);
        } else {
          // Beam fades out when satellite passes behind Earth
          beamPolygonRef.current.style.opacity = '0.04';
        }
      }

      // Update Footprint Group
      if (footprintGroupRef.current) {
        footprintGroupRef.current.setAttribute('transform', `translate(${fx.toFixed(1)}, ${fy.toFixed(1)})`);
        footprintGroupRef.current.style.opacity = isFront ? (0.4 + depthFactor * 0.55).toFixed(2) : '0.1';
      }

      // Update Data Transmission Stream towards AI Analysis Card
      if (dataStreamPathRef.current && dataPacketRef.current) {
        const destX = 420;
        const destY = 410;
        const ctrlX = (fx + destX) / 2 + 30;
        const ctrlY = (fy + destY) / 2 + 10;
        const pathData = `M ${fx.toFixed(1)},${fy.toFixed(1)} Q ${ctrlX.toFixed(1)},${ctrlY.toFixed(1)} ${destX},${destY}`;
        dataStreamPathRef.current.setAttribute('d', pathData);

        // Packet travels along the stream
        const packetProgress = (elapsed * 1.2) % 1;
        const t1 = 1 - packetProgress;
        // Quadratic bezier formula
        const px = t1 * t1 * fx + 2 * t1 * packetProgress * ctrlX + packetProgress * packetProgress * destX;
        const py = t1 * t1 * fy + 2 * t1 * packetProgress * ctrlY + packetProgress * packetProgress * destY;
        dataPacketRef.current.setAttribute('cx', px.toFixed(1));
        dataPacketRef.current.setAttribute('cy', py.toFixed(1));
        dataPacketRef.current.style.opacity = isFront ? (0.3 + Math.sin(packetProgress * Math.PI) * 0.7).toFixed(2) : '0';
      }

      animFrameRef.current = requestAnimationFrame(loop);
    };

    animFrameRef.current = requestAnimationFrame(loop);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [prefersReducedMotion]);

  // Subtle Mouse Parallax on Container (Does NOT stop orbital movement)
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (prefersReducedMotion || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const nx = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
    const ny = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
    setParallax({ x: nx * 5, y: ny * 5 });
  };

  const handleMouseLeave = () => {
    setParallax({ x: 0, y: 0 });
  };

  return (
    <div
      ref={containerRef}
      className="landing-hero-visual-wrapper"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <div
        className="hero-orbital-container"
        style={{
          transform: `translate(${parallax.x.toFixed(1)}px, ${parallax.y.toFixed(1)}px)`,
          transition: 'transform 0.3s ease-out',
        }}
      >
        {/* Stylized Orbit SVG Graphic */}
        <svg
          className="hero-orbital-svg"
          viewBox="0 0 500 500"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            {/* Globe Deep Navy Radial Core */}
            <radialGradient id="globeGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#0d2348" stopOpacity="0.95" />
              <stop offset="65%" stopColor="#08142a" stopOpacity="0.98" />
              <stop offset="100%" stopColor="#030712" stopOpacity="1" />
            </radialGradient>

            {/* Atmosphere Rim Glow */}
            <radialGradient id="atmosphereGlow" cx="50%" cy="50%" r="50%">
              <stop offset="70%" stopColor="#38bdf8" stopOpacity="0" />
              <stop offset="95%" stopColor="#38bdf8" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.6" />
            </radialGradient>

            {/* Remote Sensing Scanning Swath Gradient */}
            <linearGradient id="scientificSwathBeam" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.75" />
              <stop offset="60%" stopColor="#38bdf8" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.08" />
            </linearGradient>

            {/* Footprint Radar Pulse Radial Gradient */}
            <radialGradient id="footprintGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
              <stop offset="45%" stopColor="#10b981" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
            </radialGradient>

            {/* Data Stream Gradient */}
            <linearGradient id="dataStreamGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.1" />
              <stop offset="50%" stopColor="#10b981" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#a855f7" stopOpacity="0.75" />
            </linearGradient>
          </defs>

          {/* Outer Coordinate Grid Rings */}
          <circle cx="250" cy="250" r="235" stroke="rgba(56, 189, 248, 0.08)" strokeWidth="1" strokeDasharray="4 8" />
          <circle cx="250" cy="250" r="195" stroke="rgba(56, 189, 248, 0.12)" strokeWidth="1" />
          <circle cx="250" cy="250" r="145" stroke="rgba(168, 85, 247, 0.15)" strokeWidth="1" strokeDasharray="3 4" />

          {/* Elliptical Satellite Orbit Path */}
          <ellipse
            cx="250"
            cy="250"
            rx="205"
            ry="98"
            transform="rotate(-22 250 250)"
            stroke="rgba(56, 189, 248, 0.35)"
            strokeWidth="1.5"
            strokeDasharray="6 5"
          />

          {/* Earth Globe Base Sphere */}
          <circle cx="250" cy="250" r="110" fill="url(#globeGlow)" stroke="rgba(56, 189, 248, 0.45)" strokeWidth="1.5" />
          
          {/* Atmosphere Halo */}
          <circle cx="250" cy="250" r="110" fill="url(#atmosphereGlow)" pointerEvents="none" />

          {/* Globe Latitude & Longitude Grids */}
          <ellipse cx="250" cy="250" rx="110" ry="42" stroke="rgba(56, 189, 248, 0.22)" strokeWidth="1" fill="none" />
          <ellipse cx="250" cy="250" rx="110" ry="82" stroke="rgba(56, 189, 248, 0.14)" strokeWidth="1" fill="none" />
          <line x1="140" y1="250" x2="360" y2="250" stroke="rgba(56, 189, 248, 0.28)" strokeWidth="1" strokeDasharray="3 3" />
          <line x1="250" y1="140" x2="250" y2="360" stroke="rgba(56, 189, 248, 0.28)" strokeWidth="1" strokeDasharray="3 3" />

          {/* Stylized Continents Outlines on Earth */}
          <path
            d="M 180,215 Q 195,190 220,195 Q 235,210 230,230 Q 210,240 190,235 Z"
            fill="rgba(56, 189, 248, 0.1)"
            stroke="rgba(56, 189, 248, 0.25)"
            strokeWidth="1"
          />
          <path
            d="M 255,225 Q 275,205 305,215 Q 320,235 305,260 Q 280,270 260,250 Z"
            fill="rgba(16, 185, 129, 0.12)"
            stroke="rgba(16, 185, 129, 0.28)"
            strokeWidth="1"
          />
          <path
            d="M 215,265 Q 235,255 250,270 Q 245,295 225,300 Q 205,290 215,265 Z"
            fill="rgba(56, 189, 248, 0.08)"
            stroke="rgba(56, 189, 248, 0.2)"
            strokeWidth="1"
          />

          {/* Dynamic Remote-Sensing Footprint on Earth */}
          <g ref={footprintGroupRef} transform="translate(250, 260)" style={{ transition: 'opacity 0.2s linear' }}>
            {/* Footprint Scanning Ellipse */}
            <ellipse cx="0" cy="0" rx="28" ry="14" fill="url(#footprintGlow)" />
            <ellipse
              cx="0"
              cy="0"
              rx="28"
              ry="14"
              stroke="#38bdf8"
              strokeWidth="1.2"
              strokeDasharray="3 2"
              className="footprint-pulse"
            />
            {/* Sensor Scan Line */}
            <line x1="-20" y1="0" x2="20" y2="0" stroke="rgba(16, 185, 129, 0.7)" strokeWidth="1" />
            <line x1="0" y1="-8" x2="0" y2="8" stroke="rgba(56, 189, 248, 0.7)" strokeWidth="1" />
          </g>

          {/* Dynamic Scanning Swath Beam (Satellite to Footprint) */}
          <polygon
            ref={beamPolygonRef}
            points="120,80 220,240 280,240"
            fill="url(#scientificSwathBeam)"
            style={{ mixBlendMode: 'screen', transition: 'opacity 0.2s linear' }}
          />

          {/* Subtle Data Transmission Stream Path */}
          <path
            ref={dataStreamPathRef}
            d="M 250,260 Q 340,340 420,410"
            stroke="url(#dataStreamGrad)"
            strokeWidth="1.2"
            strokeDasharray="3 4"
            fill="none"
            className="stream-dash-anim"
          />
          {/* Animated Telemetry Micro-Packet */}
          <circle
            ref={dataPacketRef}
            cx="250"
            cy="260"
            r="3"
            fill="#a855f7"
            filter="drop-shadow(0 0 4px #a855f7)"
          />

          {/* Dynamic Orbiting Satellite Platform */}
          <g ref={satelliteGroupRef} transform="translate(120, 80) scale(1)">
            {/* Sensor Beam Focus Core */}
            <circle cx="0" cy="0" r="7" fill="#0f172a" stroke="#38bdf8" strokeWidth="1.5" />
            <circle cx="0" cy="0" r="3.5" fill="#38bdf8" />
            <circle cx="0" cy="0" r="12" stroke="rgba(56, 189, 248, 0.4)" strokeWidth="1" className="sat-radar-pulse" />

            {/* Dual Photovoltaic Solar Arrays */}
            {/* Left Solar Panel */}
            <rect x="-24" y="-5" width="14" height="10" rx="1.5" fill="#0369a1" stroke="#38bdf8" strokeWidth="0.8" />
            <line x1="-17" y1="-5" x2="-17" y2="5" stroke="rgba(255, 255, 255, 0.3)" strokeWidth="0.7" />
            <line x1="-24" y1="0" x2="-10" y2="0" stroke="rgba(255, 255, 255, 0.3)" strokeWidth="0.7" />

            {/* Right Solar Panel */}
            <rect x="10" y="-5" width="14" height="10" rx="1.5" fill="#0369a1" stroke="#38bdf8" strokeWidth="0.8" />
            <line x1="17" y1="-5" x2="17" y2="5" stroke="rgba(255, 255, 255, 0.3)" strokeWidth="0.7" />
            <line x1="10" y1="0" x2="24" y2="0" stroke="rgba(255, 255, 255, 0.3)" strokeWidth="0.7" />

            {/* Remote Sensing Instrument Sensor Pod */}
            <rect x="-3" y="6" width="6" height="4" rx="1" fill="#10b981" />
          </g>
        </svg>

        {/* 4. Layer Stack Visuals (SATELLITE -> MULTISPECTRAL -> AI ANALYSIS) */}
        <div className="hero-layer-stack">
          <div className="hero-layer-card layer-top float-card-1">
            <div className="layer-header">
              <Satellite size={14} color="#38bdf8" />
              <span>SATELLITE PLATFORMS</span>
            </div>
            <p className="layer-desc">Landsat-9 OLI-2 + Sentinel-1 C-SAR</p>
          </div>

          <div className="hero-layer-card layer-mid float-card-2">
            <div className="layer-header">
              <Layers size={14} color="#10b981" />
              <span>MULTISPECTRAL DATA</span>
            </div>
            <p className="layer-desc">Surface Reflectance (B2, B3, B4, B5, VV, VH)</p>
          </div>

          <div className="hero-layer-card layer-bot float-card-3">
            <div className="layer-header">
              <Cpu size={14} color="#a855f7" />
              <span>AI ANALYSIS</span>
            </div>
            <p className="layer-desc">SmolVLM-500M + Fine-tuned RS LoRA</p>
          </div>
        </div>
      </div>
    </div>
  );
};
