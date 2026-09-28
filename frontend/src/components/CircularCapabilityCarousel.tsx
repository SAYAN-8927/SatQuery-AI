import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Leaf,
  BarChart2,
  Clock,
  Activity,
  Radio,
  ExternalLink,
  X,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
  Atom,
  Sliders
} from 'lucide-react';

interface CapabilityItem {
  id: string;
  number: string;
  title: string;
  frontDescription: string;
  badge: string;
  techFooter: string;
  accentColor: string;
  icon: React.ReactNode;
  modal: {
    scientificMethod: string;
    requirements: string[];
    outputs: string[];
    aiInterpretation: string;
  };
}

const CAPABILITY_ITEMS: CapabilityItem[] = [
  {
    id: 'vqa',
    number: '01',
    title: 'REMOTE-SENSING VQA',
    frontDescription:
      'Ask natural-language questions about satellite scenes using the adapted SmolVLM + RS LoRA vision-language model.',
    badge: 'VLM CORE',
    techFooter: 'SmolVLM-500M • RS LoRA',
    accentColor: '#38bdf8', // Cyan / Blue
    icon: <Leaf size={22} />,
    modal: {
      scientificMethod:
        'Multimodal Vision-Language cross-attention with parameter-efficient Low-Rank Adaptation (LoRA, Rank 16) fine-tuned on optical remote sensing triplets.',
      requirements: [
        'Optical True-Color or False-Color Composite',
        'Calibrated Level-2 Surface Reflectance (RGB/NIR)',
        'PyTorch FP16 CUDA In-Memory Model Cache'
      ],
      outputs: [
        'Direct natural language explanation of canopy, topography, and surface features',
        'Grounded visual reasoning and zero-shot question answering',
        'Confidence score with audited decision grounds'
      ],
      aiInterpretation:
        'SmolVLM-500M + RS LoRA fine-tuned on 645 curated geospatial triplets without external cloud API dependencies.'
    }
  },
  {
    id: 'ndvi',
    number: '02',
    title: 'NDVI & NDWI',
    frontDescription:
      'Calculate vegetation and open-water indices from calibrated multispectral surface reflectance.',
    badge: 'SCIENTIFIC ENGINE',
    techFooter: 'B4 + B5 • B3 + B5',
    accentColor: '#10b981', // Green
    icon: <BarChart2 size={22} />,
    modal: {
      scientificMethod:
        'NDVI = (NIR - Red) / (NIR + Red) [Rouse et al., 1974] • NDWI = (Green - NIR) / (Green + NIR) [McFeeters, 1996]',
      requirements: [
        'Landsat-9 OLI-2 Level-2 Surface Reflectance',
        'B3 Green (0.56µm), B4 Red (0.65µm), B5 NIR (0.86µm)',
        'Valid geographic projection / UTM grid'
      ],
      outputs: [
        'Floating-point index rasters normalized to [-1.0, +1.0]',
        'Color-mapped false-color spatial heatmaps (Turbo & YlGn)',
        'Mean index, canopy density %, and water body area statistics'
      ],
      aiInterpretation:
        'Deterministic physics computation verified with zero mathematical hallucinations, synthesized by the agent.'
    }
  },
  {
    id: 'change',
    number: '03',
    title: 'BI-TEMPORAL CHANGE',
    frontDescription:
      'Compare spatially compatible satellite scenes across time and identify vegetation gain, loss and stability.',
    badge: 'CHANGE ANALYSIS',
    techFooter: 'ΔNDVI • 3-PANEL EVIDENCE',
    accentColor: '#f59e0b', // Amber / Orange
    icon: <Clock size={22} />,
    modal: {
      scientificMethod:
        'ΔNDVI = NDVI(after) - NDVI(before) • Vegetation Gain: ΔNDVI > +0.10 | Vegetation Loss: ΔNDVI < -0.10',
      requirements: [
        'Compatible optical scenes with identical WRS-2 Path/Row (e.g. 141/040)',
        'Identical spatial extent, projection, and pixel resolution (30m)',
        'B4 Red and B5 NIR bands for both acquisition dates'
      ],
      outputs: [
        'Before RGB & NDVI, After RGB & NDVI',
        '3-Panel Comparative Triplet & ΔNDVI difference heatmap',
        'Gain / Loss / Stable terrain area percentages'
      ],
      aiInterpretation:
        'VLM-assisted bi-temporal change interpretation explaining spatial shifts, seasonality, and environmental context.'
    }
  },
  {
    id: 'spectral',
    number: '04',
    title: 'SPECTRAL ANALYSIS',
    frontDescription:
      'Analyze Blue, Green, Red and NIR reflectance to reveal the spectral characteristics of a scene.',
    badge: 'MULTISPECTRAL',
    techFooter: 'B2 • B3 • B4 • B5',
    accentColor: '#ec4899', // Pink / Magenta
    icon: <Activity size={22} />,
    modal: {
      scientificMethod:
        'Multispectral radiometry signature extraction across B2 (0.48µm), B3 (0.56µm), B4 (0.65µm), and B5 (0.86µm) • Chlorophyll absorption vs mesophyll scattering',
      requirements: [
        '4 calibrated optical surface reflectance bands',
        'Atmospheric correction (Level-2 Science Product)',
        'Cloud masking via QA_PIXEL'
      ],
      outputs: [
        '4-Band Surface Reflectance signature curve',
        'Radiometric peak and water absorption band diagnostics',
        'Scene index tagging (Healthy Vegetation, Turbid Water, Barren Soil)'
      ],
      aiInterpretation:
        'Autonomous agent spectral classifier confirming physical radiometric consistency against standard USGS spectral libraries.'
    }
  },
  {
    id: 'fusion',
    number: '05',
    title: 'OPTICAL + SAR FUSION',
    frontDescription:
      'Combine Landsat optical imagery with Sentinel-1 C-SAR to analyze vegetation, scattering and surface conditions.',
    badge: 'MULTIMODAL',
    techFooter: 'Landsat • Sentinel-1',
    accentColor: '#a855f7', // Purple
    icon: <Radio size={22} />,
    modal: {
      scientificMethod:
        'Passive optical reflectance fused with active microwave backscatter: σ° VV and σ° VH (in decibels) • Radar Vegetation Index: RVI = 4 * VH / (VV + VH)',
      requirements: [
        'Landsat-9 OLI-2 Optical Composite (Bands B2-B5)',
        'Sentinel-1A C-SAR Level-1 GRD calibrated backscatter (VV + VH)',
        'Co-registered spatial bounding box'
      ],
      outputs: [
        '4-Panel Multimodal Fusion Composite (Optical RGB, NDVI, SAR Radar, Fusion Overlay)',
        'Dielectric volume vs. surface scattering metrics',
        'Cross-sensor agreement percentage & consensus confidence'
      ],
      aiInterpretation:
        'All-weather structural radar validation confirming optical canopy estimates through clouds and atmospheric haze.'
    }
  }
];

const BASE_SPEED = -0.32; // degrees per frame (smooth continuous orbital drift)
const TOTAL_ITEMS = CAPABILITY_ITEMS.length;
const ANGLE_PER_ITEM = 360 / TOTAL_ITEMS; // 72 degrees

export const CircularCapabilityCarousel: React.FC = () => {
  const [activeIndex, setActiveIndex] = useState<number>(0);
  const [selectedCard, setSelectedCard] = useState<CapabilityItem | null>(null);
  const [radius, setRadius] = useState<number>(380);

  const containerRef = useRef<HTMLDivElement>(null);
  const cylinderRef = useRef<HTMLDivElement>(null);

  // Animation & Physics Refs (avoids 60fps React re-renders)
  const rotationRef = useRef<number>(0);
  const currentSpeedRef = useRef<number>(BASE_SPEED);
  const targetSpeedRef = useRef<number>(BASE_SPEED);
  const isDraggingRef = useRef<boolean>(false);
  const dragStartXRef = useRef<number>(0);
  const dragStartRotationRef = useRef<number>(0);
  const hasDraggedRef = useRef<boolean>(false);
  const lastPointerXRef = useRef<number>(0);
  const lastPointerTimeRef = useRef<number>(0);
  const pointerVelocityRef = useRef<number>(0);
  const isModalOpenRef = useRef<boolean>(false);
  const prefersReducedMotionRef = useRef<boolean>(false);
  const reqAnimRef = useRef<number | null>(null);
  const activeIndexRef = useRef<number>(0);

  // Responsive radius calculation
  const updateRadius = useCallback(() => {
    if (typeof window !== 'undefined') {
      const width = window.innerWidth;
      if (width > 1200) {
        setRadius(380);
      } else if (width > 900) {
        setRadius(320);
      } else if (width > 640) {
        setRadius(250);
      } else {
        setRadius(190);
      }
    }
  }, []);

  useEffect(() => {
    updateRadius();
    window.addEventListener('resize', updateRadius);
    return () => window.removeEventListener('resize', updateRadius);
  }, [updateRadius]);

  // Reduced motion preference check
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      prefersReducedMotionRef.current = mediaQuery.matches;
      const handleMotionChange = (e: MediaQueryListEvent) => {
        prefersReducedMotionRef.current = e.matches;
      };
      mediaQuery.addEventListener('change', handleMotionChange);
      return () => mediaQuery.removeEventListener('change', handleMotionChange);
    }
  }, []);

  // Sync modal state with ref to control rotation pause
  useEffect(() => {
    isModalOpenRef.current = selectedCard !== null;
    if (selectedCard) {
      targetSpeedRef.current = 0;
      currentSpeedRef.current = 0;
    } else {
      targetSpeedRef.current = BASE_SPEED;
    }
  }, [selectedCard]);

  // Close modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && selectedCard) {
        setSelectedCard(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedCard]);

  // Continuous Orbital Physics Loop
  useEffect(() => {
    const animate = () => {
      if (!isModalOpenRef.current && !prefersReducedMotionRef.current) {
        if (!isDraggingRef.current) {
          // Smooth physical lerp toward target speed (steering damping)
          currentSpeedRef.current += (targetSpeedRef.current - currentSpeedRef.current) * 0.06;
          rotationRef.current = (rotationRef.current + currentSpeedRef.current) % 360;
        }

        // Apply 3D transform directly to cylinder element for 60fps GPU acceleration
        if (cylinderRef.current) {
          cylinderRef.current.style.transform = `rotateY(${rotationRef.current}deg)`;
        }

        // Track active front card index
        const normalized = ((-rotationRef.current % 360) + 360) % 360;
        const frontIndex = Math.round(normalized / ANGLE_PER_ITEM) % TOTAL_ITEMS;
        if (frontIndex !== activeIndexRef.current) {
          activeIndexRef.current = frontIndex;
          setActiveIndex(frontIndex);
        }
      }

      reqAnimRef.current = requestAnimationFrame(animate);
    };

    reqAnimRef.current = requestAnimationFrame(animate);
    return () => {
      if (reqAnimRef.current) cancelAnimationFrame(reqAnimRef.current);
    };
  }, []);

  // Mouse Steering Handlers (ROTATION NEVER STOPS ON HOVER)
  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!containerRef.current || isModalOpenRef.current || prefersReducedMotionRef.current) return;

    if (isDraggingRef.current) {
      // Manual Drag Mode
      const deltaX = e.clientX - dragStartXRef.current;
      if (Math.abs(deltaX) > 6) {
        hasDraggedRef.current = true;
      }
      rotationRef.current = dragStartRotationRef.current + deltaX * 0.38;
      if (cylinderRef.current) {
        cylinderRef.current.style.transform = `rotateY(${rotationRef.current}deg)`;
      }

      // Track drag velocity for inertia release
      const now = performance.now();
      const dt = now - lastPointerTimeRef.current;
      if (dt > 0) {
        pointerVelocityRef.current = ((e.clientX - lastPointerXRef.current) / dt) * 10;
      }
      lastPointerXRef.current = e.clientX;
      lastPointerTimeRef.current = now;
    } else {
      // Mouse Steering Mode
      // Normalized X: -1.0 (far left) to 0.0 (center) to +1.0 (far right)
      const rect = containerRef.current.getBoundingClientRect();
      const normX = Math.max(-1, Math.min(1, ((e.clientX - rect.left) / rect.width) * 2 - 1));

      if (normX < -0.15) {
        // Cursor on left side -> steer faster to the left
        const intensity = (Math.abs(normX) - 0.15) / 0.85;
        targetSpeedRef.current = BASE_SPEED - intensity * 1.8;
      } else if (normX > 0.15) {
        // Cursor on right side -> steer to the right
        const intensity = (normX - 0.15) / 0.85;
        targetSpeedRef.current = BASE_SPEED + intensity * 2.2;
      } else {
        // Cursor near center -> normal slow automatic rotation
        targetSpeedRef.current = BASE_SPEED;
      }
    }
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isModalOpenRef.current) return;
    isDraggingRef.current = true;
    hasDraggedRef.current = false;
    dragStartXRef.current = e.clientX;
    dragStartRotationRef.current = rotationRef.current;
    lastPointerXRef.current = e.clientX;
    lastPointerTimeRef.current = performance.now();
    pointerVelocityRef.current = 0;
  };

  const handlePointerUp = () => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      // Apply smooth drag inertia
      if (hasDraggedRef.current) {
        currentSpeedRef.current = pointerVelocityRef.current * 0.35;
      }
      // Target speed returns to base speed smoothly
      targetSpeedRef.current = BASE_SPEED;
    }
  };

  const handlePointerLeave = () => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
    }
    // Cursor left carousel viewport -> smoothly return to base automatic rotation
    targetSpeedRef.current = BASE_SPEED;
  };

  // Card Click: only opens modal if user wasn't actively dragging
  const handleCardClick = (item: CapabilityItem) => {
    if (hasDraggedRef.current) return;
    setSelectedCard(item);
  };

  // Keyboard accessibility
  const handleKeyDown = (e: React.KeyboardEvent, item: CapabilityItem) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setSelectedCard(item);
    }
  };

  // Navigation step buttons (< and >)
  const rotateStep = (direction: 'prev' | 'next') => {
    const delta = direction === 'next' ? -ANGLE_PER_ITEM : ANGLE_PER_ITEM;
    rotationRef.current = Math.round((rotationRef.current + delta) / ANGLE_PER_ITEM) * ANGLE_PER_ITEM;
    if (cylinderRef.current) {
      cylinderRef.current.style.transform = `rotateY(${rotationRef.current}deg)`;
    }
    targetSpeedRef.current = BASE_SPEED;
  };

  // Snap to specific index (from bottom indicators)
  const snapToIndex = (index: number) => {
    rotationRef.current = -index * ANGLE_PER_ITEM;
    if (cylinderRef.current) {
      cylinderRef.current.style.transform = `rotateY(${rotationRef.current}deg)`;
    }
    targetSpeedRef.current = BASE_SPEED;
  };

  return (
    <div className="circular-carousel-wrapper">
      {/* Dynamic Interaction Instruction Ribbon */}
      <div className="carousel-instruction-bar" role="status">
        <div className="instruction-item">
          <Atom size={15} className="spin-slow" color="#38bdf8" />
          <span>Explore the capabilities • Move your cursor to steer the orbit • Drag to rotate • Click a card for details</span>
        </div>
      </div>

      {/* 3D Viewport */}
      <div
        ref={containerRef}
        className={`carousel-viewport ${isDraggingRef.current ? 'is-dragging' : ''}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        style={{ touchAction: 'pan-y' }}
      >
        {/* Orbital Center Plane Ring & Core Pulse */}
        <div
          className="carousel-center-axis"
          style={{
            transform: `rotateX(75deg) translateZ(-80px)`,
            width: radius * 2 + 100,
            height: radius * 2 + 100,
          }}
        >
          <div className="orbital-ring-dashed" />
          <div className="orbital-pulse-core" />
        </div>

        {/* 3D Cylinder with All 5 Cards */}
        <div ref={cylinderRef} className="carousel-cylinder">
          {CAPABILITY_ITEMS.map((item, index) => {
            const angle = index * ANGLE_PER_ITEM;
            const isCenter = index === activeIndex;

            return (
              <div
                key={item.id}
                className={`orbital-card-slot ${isCenter ? 'is-front-center' : ''}`}
                style={{
                  transform: `rotateY(${angle}deg) translateZ(${radius}px)`,
                }}
              >
                {/* 3D Card with Separate Front & Back Faces */}
                <div
                  className="orbital-card"
                  onClick={() => handleCardClick(item)}
                  onKeyDown={(e) => handleKeyDown(e, item)}
                  tabIndex={0}
                  role="button"
                  aria-label={`Capability ${item.number}: ${item.title}. Click to view detailed scientific specifications.`}
                  style={{
                    borderColor: isCenter ? item.accentColor : 'rgba(56, 189, 248, 0.22)',
                    boxShadow: isCenter
                      ? `0 14px 40px rgba(0, 0, 0, 0.7), 0 0 30px ${item.accentColor}35`
                      : '0 8px 25px rgba(0, 0, 0, 0.55)',
                  }}
                >
                  {/* FRONT FACE (Faces outward in 3D orbit) */}
                  <div className="card-face card-front">
                    <div className="card-top-row">
                      <span className="card-number">{item.number}</span>
                      <span
                        className="card-badge"
                        style={{
                          color: item.accentColor,
                          borderColor: `${item.accentColor}45`,
                          background: `${item.accentColor}12`,
                        }}
                      >
                        {item.badge}
                      </span>
                      <div
                        className="card-icon-pill"
                        style={{
                          color: item.accentColor,
                          background: `${item.accentColor}18`,
                          borderColor: `${item.accentColor}35`,
                        }}
                      >
                        {item.icon}
                      </div>
                    </div>

                    <h3 className="card-headline">{item.title}</h3>
                    <p className="card-description">{item.frontDescription}</p>

                    <div className="card-bottom-row">
                      <span className="card-tech-footer">{item.techFooter}</span>
                      <span className="card-click-hint" style={{ color: item.accentColor }}>
                        <span>CLICK FOR DETAILS</span>
                        <ExternalLink size={12} />
                      </span>
                    </div>
                  </div>

                  {/* BACK FACE (Faces inward toward cylinder center - Minimal Aerospace Chassis) */}
                  <div className="card-face card-back">
                    <div className="back-chassis-grid" />
                    <div className="back-chassis-content">
                      <div className="back-telemetry-tag">SATQUERY AI // ORBITAL BUS</div>
                      <div
                        className="back-chassis-icon"
                        style={{
                          color: item.accentColor,
                          background: `${item.accentColor}15`,
                          borderColor: `${item.accentColor}35`,
                        }}
                      >
                        <ShieldCheck size={26} />
                      </div>
                      <div className="back-chassis-number">{item.number}</div>
                      <div className="back-chassis-title">REMOTE SENSING ENGINE</div>
                      <div className="back-chassis-payload">ORBITAL SENSOR PAYLOAD</div>
                      <div className="back-chassis-sysid">SYS.ID // SQ-RS-{item.number}</div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Orbit Controls & Active Card Indicator: 01 02 [03] 04 05 */}
      <div className="orbital-controls-wrapper">
        <button
          onClick={() => rotateStep('prev')}
          className="carousel-nav-arrow"
          aria-label="Previous capability"
          title="Previous Capability"
        >
          <ChevronLeft size={20} />
        </button>

        <div className="orbital-focus-bar" role="tablist" aria-label="Capabilities indicator">
          {CAPABILITY_ITEMS.map((item, idx) => {
            const isActive = idx === activeIndex;
            return (
              <button
                key={item.id}
                role="tab"
                aria-selected={isActive}
                className={`orbital-focus-chip ${isActive ? 'active' : ''}`}
                onClick={() => snapToIndex(idx)}
                title={`Jump to ${item.title}`}
                style={{
                  color: isActive ? item.accentColor : undefined,
                  borderColor: isActive ? `${item.accentColor}70` : undefined,
                  background: isActive ? `${item.accentColor}18` : undefined,
                  boxShadow: isActive ? `0 0 15px ${item.accentColor}30` : undefined,
                }}
              >
                <span className="focus-chip-num">{item.number}</span>
                <span className="focus-chip-title">{item.title}</span>
              </button>
            );
          })}
        </div>

        <button
          onClick={() => rotateStep('next')}
          className="carousel-nav-arrow"
          aria-label="Next capability"
          title="Next Capability"
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* SCIENTIFIC DETAIL MODAL (Opens on Card Click) */}
      {selectedCard && (
        <div className="capability-modal-backdrop" onClick={() => setSelectedCard(null)}>
          <div
            className="capability-modal-dialog"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-cap-title"
            style={{
              borderColor: `${selectedCard.accentColor}60`,
              boxShadow: `0 20px 60px rgba(0, 0, 0, 0.85), 0 0 40px ${selectedCard.accentColor}25`,
            }}
          >
            {/* Modal Header */}
            <div className="modal-top-bar">
              <div className="modal-title-group">
                <span
                  className="modal-badge"
                  style={{
                    color: selectedCard.accentColor,
                    borderColor: `${selectedCard.accentColor}50`,
                    background: `${selectedCard.accentColor}15`,
                  }}
                >
                  {selectedCard.number} • {selectedCard.badge}
                </span>
                <h3 id="modal-cap-title" className="modal-title">
                  {selectedCard.title}
                </h3>
              </div>
              <button
                onClick={() => setSelectedCard(null)}
                className="modal-close-btn"
                aria-label="Close details"
              >
                <X size={20} />
              </button>
            </div>

            <p className="modal-summary-text">{selectedCard.frontDescription}</p>

            {/* Modal Body Sections */}
            <div className="modal-content-grid">
              {/* Scientific Method */}
              <div className="modal-section-card">
                <div className="modal-section-label" style={{ color: selectedCard.accentColor }}>
                  <Atom size={15} />
                  <span>SCIENTIFIC METHOD & FORMULATION</span>
                </div>
                <div className="modal-formula-box">
                  <code>{selectedCard.modal.scientificMethod}</code>
                </div>
              </div>

              {/* Requirements & Input Modalities */}
              <div className="modal-section-card">
                <div className="modal-section-label" style={{ color: selectedCard.accentColor }}>
                  <Sliders size={15} />
                  <span>REQUIREMENTS & SENSOR INPUTS</span>
                </div>
                <ul className="modal-bullets-list">
                  {selectedCard.modal.requirements.map((req, i) => (
                    <li key={i}>
                      <CheckCircle2 size={13} color={selectedCard.accentColor} />
                      <span>{req}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Output Artifacts */}
              <div className="modal-section-card">
                <div className="modal-section-label" style={{ color: selectedCard.accentColor }}>
                  <BarChart2 size={15} />
                  <span>OUTPUT ARTIFACTS & EVIDENCE</span>
                </div>
                <ul className="modal-bullets-list">
                  {selectedCard.modal.outputs.map((out, i) => (
                    <li key={i}>
                      <span className="bullet-dot" style={{ background: selectedCard.accentColor }} />
                      <span>{out}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* AI Interpretation */}
              <div className="modal-section-card highlight">
                <div className="modal-section-label" style={{ color: selectedCard.accentColor }}>
                  <ShieldCheck size={15} />
                  <span>AI SYNTHESIS & AUDITABLE GUARANTEE</span>
                </div>
                <p className="modal-ai-desc">{selectedCard.modal.aiInterpretation}</p>
              </div>
            </div>

            {/* Modal Action Bar */}
            <div className="modal-actions-bar">
              <span className="modal-tech-tag">{selectedCard.techFooter}</span>
              <button
                onClick={() => setSelectedCard(null)}
                className="modal-action-close-btn"
                style={{
                  background: `${selectedCard.accentColor}20`,
                  borderColor: selectedCard.accentColor,
                  color: '#f8fafc',
                }}
              >
                CLOSE READOUT
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
