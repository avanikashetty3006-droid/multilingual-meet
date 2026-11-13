import React, { useEffect, useRef, useState, useCallback } from 'react';

/**
 * VAAK Logo Reveal Animation
 * Dynamically constructs the 3D V emblem, orbital ring, and 'VAAK' wordmark
 * from world particles and vector light sweeps, rather than sudden showing.
 *
 * Theme Palette:
 * - Onyx Black: #090809
 * - Deep Aubergine: #171019
 * - Dark Eggplant: #211526
 * - Smoked Plum: #302034
 * - Muted Aubergine: #49334D
 * - Soft Plum: #705675
 * - Muted Lilac: #A28FA5
 * - Warm White: #E8E2E8
 */

const PALETTE = {
  onyx: '#090809',
  blackAubergine: '#100B10',
  deepAubergine: '#171019',
  darkEggplant: '#211526',
  smokedPlum: '#302034',
  mutedAubergine: '#49334D',
  softPlum: '#705675',
  mutedLilac: '#A28FA5',
  warmWhite: '#E8E2E8',
};

export function LogoReveal({ onComplete }) {
  const canvasRef = useRef(null);
  const [stageName, setStageName] = useState('Connecting Continents');
  const [isConstructed, setIsConstructed] = useState(false);
  const [showEnterBtn, setShowEnterBtn] = useState(false);

  // Check prefers-reduced-motion
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      if (mediaQuery.matches) {
        setIsConstructed(true);
        setShowEnterBtn(true);
      }
    }
  }, []);

  const handleFinish = useCallback(() => {
    if (onComplete) onComplete();
  }, [onComplete]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    // World Map Cluster Centroids (normalized -1..1)
    const worldClusters = [
      { cx: -0.55, cy: -0.22, count: 160, spreadX: 0.17, spreadY: 0.14 }, // North America
      { cx: -0.36, cy: 0.24, count: 110, spreadX: 0.11, spreadY: 0.18 },  // South America
      { cx: 0.04, cy: -0.26, count: 130, spreadX: 0.10, spreadY: 0.10 },   // Europe
      { cx: 0.07, cy: 0.12, count: 150, spreadX: 0.12, spreadY: 0.20 },   // Africa
      { cx: 0.40, cy: -0.18, count: 220, spreadX: 0.22, spreadY: 0.15 },  // Asia
      { cx: 0.30, cy: -0.01, count: 140, spreadX: 0.07, spreadY: 0.08 },  // India hub
      { cx: 0.60, cy: 0.32, count: 100, spreadX: 0.12, spreadY: 0.10 },   // Oceania
    ];

    const commHubs = [
      { x: -0.55, y: -0.22 },
      { x: 0.04, y: -0.26 },
      { x: 0.07, y: 0.12 },
      { x: 0.30, y: -0.01 },
      { x: 0.50, y: -0.16 },
      { x: 0.60, y: 0.32 },
    ];

    // Compute relative logo target points (scaled to screen size)
    const getLogoTargets = () => {
      const cx = width / 2;
      const cy = height / 2 - 40;
      const scale = Math.min(width, height) * 0.0016;

      const targets = [];

      // 1. Orbital Ring targets (elliptical curve tilted ~ -18 deg)
      const ringTilt = -0.28;
      const rx = 160 * scale;
      const ry = 42 * scale;
      for (let i = 0; i < 280; i++) {
        const theta = (i / 280) * Math.PI * 2;
        const px = Math.cos(theta) * rx;
        const py = Math.sin(theta) * ry;
        // Rotate by ringTilt
        const rotX = px * Math.cos(ringTilt) - py * Math.sin(ringTilt);
        const rotY = px * Math.sin(ringTilt) + py * Math.cos(ringTilt);
        targets.push({ x: cx + rotX, y: cy + rotY + 10 * scale, part: 'ring', order: i / 280 });
      }

      // 2. 3D Faceted 'V' emblem targets
      // Left wing outer curve
      for (let t = 0; t <= 1; t += 0.02) {
        const x = -80 * (1 - t) + -4 * t;
        const y = -65 * (1 - t) + 40 * t;
        targets.push({ x: cx + x * scale, y: cy + y * scale, part: 'v_left', order: t });
      }
      // Right wing outer sharp angle
      for (let t = 0; t <= 1; t += 0.02) {
        const x = -4 * (1 - t) + 78 * t;
        const y = 40 * (1 - t) + -72 * t;
        targets.push({ x: cx + x * scale, y: cy + y * scale, part: 'v_right', order: t });
      }
      // Center 3D facet spine & depth
      for (let t = 0; t <= 1; t += 0.03) {
        const x = -5 * (1 - t) + 12 * t;
        const y = 40 * (1 - t) + -18 * t;
        targets.push({ x: cx + x * scale, y: cy + y * scale, part: 'v_facet', order: t });
      }

      // 3. 'V A A K' letters below
      const textY = cy + 115 * scale;
      const fontSpread = 44 * scale;

      // Letter 'V' at cx - 1.5 * fontSpread
      const vX = cx - 1.6 * fontSpread;
      for (let t = 0; t <= 1; t += 0.05) {
        targets.push({ x: vX - 16 * (1 - t) * scale, y: textY - 20 * (1 - t) * scale, part: 'text', order: 0.1 });
        targets.push({ x: vX + 16 * t * scale, y: textY - 20 * (1 - t) * scale, part: 'text', order: 0.1 });
      }
      // Letter 'A' (inverted V without bar) at cx - 0.5 * fontSpread
      const a1X = cx - 0.55 * fontSpread;
      for (let t = 0; t <= 1; t += 0.05) {
        targets.push({ x: a1X - 14 * t * scale, y: textY + 20 * t * scale, part: 'text', order: 0.3 });
        targets.push({ x: a1X + 14 * t * scale, y: textY + 20 * t * scale, part: 'text', order: 0.3 });
      }
      // Letter 'A' (inverted V without bar) at cx + 0.5 * fontSpread
      const a2X = cx + 0.55 * fontSpread;
      for (let t = 0; t <= 1; t += 0.05) {
        targets.push({ x: a2X - 14 * t * scale, y: textY + 20 * t * scale, part: 'text', order: 0.5 });
        targets.push({ x: a2X + 14 * t * scale, y: textY + 20 * t * scale, part: 'text', order: 0.5 });
      }
      // Letter 'K' at cx + 1.6 * fontSpread
      const kX = cx + 1.6 * fontSpread;
      for (let t = 0; t <= 1; t += 0.05) {
        targets.push({ x: kX - 12 * scale, y: textY + (-20 + 40 * t) * scale, part: 'text', order: 0.7 });
        targets.push({ x: kX - 12 * (1 - t) * scale + 14 * t * scale, y: textY - 20 * t * scale, part: 'text', order: 0.75 });
        targets.push({ x: kX - 12 * (1 - t) * scale + 14 * t * scale, y: textY + 20 * t * scale, part: 'text', order: 0.8 });
      }

      return targets;
    };

    const logoTargets = getLogoTargets();
    const particleColors = [
      PALETTE.warmWhite,
      PALETTE.mutedLilac,
      PALETTE.softPlum,
      PALETTE.mutedAubergine,
      '#ffffff',
    ];

    // Initialize Particles
    const particles = [];
    worldClusters.forEach((cluster) => {
      for (let i = 0; i < cluster.count; i++) {
        const rx = (Math.random() + Math.random() - 1) * cluster.spreadX;
        const ry = (Math.random() + Math.random() - 1) * cluster.spreadY;
        const originX = width / 2 + (cluster.cx + rx) * (width * 0.44);
        const originY = height / 2 + (cluster.cy + ry) * (height * 0.44);

        // Assign a target in the logo
        const targetObj = logoTargets[particles.length % logoTargets.length];

        particles.push({
          x: originX + (Math.random() - 0.5) * 15,
          y: originY + (Math.random() - 0.5) * 15,
          originX,
          originY,
          targetX: targetObj.x,
          targetY: targetObj.y,
          part: targetObj.part,
          order: targetObj.order || 0,
          size: Math.random() * 2.2 + 1.0,
          baseSize: Math.random() * 2.2 + 1.0,
          color: particleColors[Math.floor(Math.random() * particleColors.length)],
          shimmerSpeed: 0.025 + Math.random() * 0.04,
          shimmerOffset: Math.random() * Math.PI * 2,
        });
      }
    });

    const startTime = performance.now();

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;

      // Update stage indicators
      if (elapsed < 2200) {
        setStageName('Connecting Continents');
      } else if (elapsed < 4200) {
        setStageName('Global Language Network');
      } else if (elapsed < 6000) {
        setStageName('Convergence & Alignment');
      } else if (elapsed < 8800) {
        setStageName('Constructing VAAK Emblem');
      } else {
        setStageName('VAAK Activated');
        setIsConstructed(true);
        setShowEnterBtn(true);
      }

      // 1. Clear with Deep Aubergine / Onyx Background
      ctx.fillStyle = PALETTE.onyx;
      ctx.fillRect(0, 0, width, height);

      // Atmospheric radial glow
      const cx = width / 2;
      const cy = height / 2 - 30;
      const radGrad = ctx.createRadialGradient(cx, cy, 20, cx, cy, width * 0.6);
      radGrad.addColorStop(0, 'rgba(48, 32, 52, 0.45)');
      radGrad.addColorStop(0.4, 'rgba(23, 16, 25, 0.3)');
      radGrad.addColorStop(1, 'rgba(9, 8, 9, 0)');
      ctx.fillStyle = radGrad;
      ctx.fillRect(0, 0, width, height);

      // 2. Render Communication Arcs (Stages 1 & 2)
      if (elapsed < 5800) {
        const arcAlpha =
          elapsed < 4200
            ? Math.min(0.35, elapsed / 2000)
            : Math.max(0, (5800 - elapsed) / 1600) * 0.35;

        ctx.lineWidth = 1.2;
        commHubs.forEach((hubA, idx) => {
          const hubB = commHubs[(idx + 2) % commHubs.length];
          const x1 = width / 2 + hubA.x * (width * 0.44);
          const y1 = height / 2 + hubA.y * (height * 0.44);
          const x2 = width / 2 + hubB.x * (width * 0.44);
          const y2 = height / 2 + hubB.y * (height * 0.44);

          const midX = (x1 + x2) / 2;
          const midY = (y1 + y2) / 2 - 35;

          ctx.beginPath();
          ctx.strokeStyle = PALETTE.softPlum;
          ctx.globalAlpha = arcAlpha;
          ctx.moveTo(x1, y1);
          ctx.quadraticCurveTo(midX, midY, x2, y2);
          ctx.stroke();

          // Data Pulse along arc
          const pulseT = (elapsed * 0.0007 + idx * 0.22) % 1;
          const px = (1 - pulseT) * (1 - pulseT) * x1 + 2 * (1 - pulseT) * pulseT * midX + pulseT * pulseT * x2;
          const py = (1 - pulseT) * (1 - pulseT) * y1 + 2 * (1 - pulseT) * pulseT * midY + pulseT * pulseT * y2;

          ctx.fillStyle = PALETTE.warmWhite;
          ctx.globalAlpha = arcAlpha * 2.2;
          ctx.beginPath();
          ctx.arc(px, py, 2.5, 0, Math.PI * 2);
          ctx.fill();
        });
        ctx.globalAlpha = 1.0;
      }

      // 3. Progressive Construction of the Emblem & Wordmark (Stage 4: 6000ms - 9000ms)
      if (elapsed > 5800) {
        const constructT = Math.min(1, (elapsed - 5800) / 2800);
        const scale = Math.min(width, height) * 0.0016;

        ctx.save();
        ctx.translate(cx, cy);

        // A. Draw the Orbital Elliptical Ring progressively
        const ringProgress = Math.min(1, constructT * 1.3);
        if (ringProgress > 0) {
          ctx.save();
          ctx.rotate(-0.28);
          ctx.beginPath();
          ctx.ellipse(0, 10 * scale, 160 * scale, 42 * scale, 0, 0, Math.PI * 2 * ringProgress);
          ctx.strokeStyle = PALETTE.softPlum;
          ctx.lineWidth = 4 * scale;
          ctx.shadowColor = PALETTE.mutedLilac;
          ctx.shadowBlur = 14;
          ctx.stroke();

          // Laser head on ring
          if (ringProgress < 1) {
            const angle = Math.PI * 2 * ringProgress;
            const hx = Math.cos(angle) * (160 * scale);
            const hy = 10 * scale + Math.sin(angle) * (42 * scale);
            ctx.fillStyle = '#ffffff';
            ctx.shadowBlur = 18;
            ctx.beginPath();
            ctx.arc(hx, hy, 4.5 * scale, 0, Math.PI * 2);
            ctx.fill();
          }
          ctx.restore();
        }

        // B. Draw the 3D Faceted 'V' Wireframe & Facets progressively
        const vProgress = Math.max(0, Math.min(1, (constructT - 0.2) * 1.4));
        if (vProgress > 0) {
          ctx.save();

          // Left metallic wing facet
          ctx.beginPath();
          ctx.moveTo(-82 * scale, -68 * scale);
          ctx.quadraticCurveTo(-45 * scale, -62 * scale, -2 * scale, (40 * scale) * vProgress);
          ctx.lineTo((-16 * scale) * vProgress, (10 * scale) * vProgress);
          ctx.closePath();

          const gradLeft = ctx.createLinearGradient(-82 * scale, -68 * scale, 0, 40 * scale);
          gradLeft.addColorStop(0, 'rgba(232, 226, 232, ' + (vProgress * 0.9) + ')');
          gradLeft.addColorStop(0.5, 'rgba(162, 143, 165, ' + (vProgress * 0.7) + ')');
          gradLeft.addColorStop(1, 'rgba(48, 32, 52, ' + (vProgress * 0.8) + ')');
          ctx.fillStyle = gradLeft;
          ctx.shadowColor = 'rgba(162, 143, 165, 0.4)';
          ctx.shadowBlur = 16;
          ctx.fill();

          // Right metallic wing facet
          ctx.beginPath();
          ctx.moveTo(-2 * scale, (40 * scale) * vProgress);
          ctx.lineTo((78 * scale) * vProgress, (-72 * scale) * vProgress);
          ctx.lineTo((38 * scale) * vProgress, (-36 * scale) * vProgress);
          ctx.closePath();

          const gradRight = ctx.createLinearGradient(0, 40 * scale, 78 * scale, -72 * scale);
          gradRight.addColorStop(0, 'rgba(73, 51, 77, ' + (vProgress * 0.85) + ')');
          gradRight.addColorStop(0.5, 'rgba(162, 143, 165, ' + (vProgress * 0.75) + ')');
          gradRight.addColorStop(1, 'rgba(232, 226, 232, ' + (vProgress * 0.95) + ')');
          ctx.fillStyle = gradRight;
          ctx.fill();

          // Sharp crest lines
          ctx.strokeStyle = PALETTE.warmWhite;
          ctx.lineWidth = 1.5 * scale;
          ctx.beginPath();
          ctx.moveTo(-82 * scale, -68 * scale);
          ctx.lineTo(-2 * scale, 40 * scale);
          ctx.lineTo(78 * scale, -72 * scale);
          ctx.stroke();

          ctx.restore();
        }

        // C. Construct the Wordmark "V A A K"
        const textProgress = Math.max(0, Math.min(1, (constructT - 0.45) * 1.8));
        if (textProgress > 0) {
          ctx.save();
          ctx.font = `800 ${28 * scale}px 'Outfit', sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.letterSpacing = '0.35em';

          const textY = 115 * scale;
          ctx.fillStyle = `rgba(232, 226, 232, ${textProgress * 0.95})`;
          ctx.shadowColor = 'rgba(162, 143, 165, 0.5)';
          ctx.shadowBlur = 12;
          ctx.fillText('V A A K', 0, textY);
          ctx.restore();
        }

        ctx.restore();
      }

      // 4. Update and Render Particles
      particles.forEach((p) => {
        if (elapsed < 2200) {
          // Gentle orbital drift in world clusters
          const drift = Math.sin(elapsed * 0.0016 + p.shimmerOffset) * 2;
          p.x = p.originX + drift;
          p.y = p.originY + Math.cos(elapsed * 0.0016 + p.shimmerOffset) * 2;
          p.size = p.baseSize;
        } else if (elapsed < 4200) {
          // Shimmering network excitation
          const wave = Math.sin(elapsed * p.shimmerSpeed + p.shimmerOffset);
          p.size = p.baseSize * (1 + 0.4 * wave);
          p.x += Math.sin(elapsed * 0.002 + p.shimmerOffset) * 0.7;
          p.y += Math.cos(elapsed * 0.002 + p.shimmerOffset) * 0.7;
        } else if (elapsed < 6000) {
          // Convergence: magnetic vortex pull to center
          const t = (elapsed - 4200) / 1800;
          const ease = t * t;
          const angle = Math.atan2(p.y - cy, p.x - cx) + 0.08;
          const dist = Math.hypot(p.x - cx, p.y - cy);
          const nextDist = dist * (1 - ease * 0.07);

          p.x = cx + Math.cos(angle) * nextDist;
          p.y = cy + Math.sin(angle) * nextDist;
          p.size = p.baseSize * (1.1 - ease * 0.2);
        } else if (elapsed < 8800) {
          // Assembly: migrate directly into the logo target contour
          const assembleT = Math.min(1, (elapsed - 6000) / 2500);
          const ease = assembleT * assembleT * (3 - 2 * assembleT);
          p.x += (p.targetX - p.x) * (0.08 + ease * 0.12);
          p.y += (p.targetY - p.y) * (0.08 + ease * 0.12);
          p.size = p.baseSize * 1.05;
        } else {
          // Settle into ambient radiant halo
          const settleT = Math.min(1, (elapsed - 8800) / 1500);
          p.x += Math.cos(p.shimmerOffset + elapsed * 0.0004) * 0.25;
          p.y += Math.sin(p.shimmerOffset + elapsed * 0.0004) * 0.25;
          ctx.globalAlpha = Math.max(0.12, 1 - settleT * 0.7);
        }

        // Draw particle
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0.7, p.size), 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1.0;
      });

      // Continue animation loop until complete
      if (elapsed < 11500) {
        animationFrameId = requestAnimationFrame(animate);
      } else {
        setShowEnterBtn(true);
        setIsConstructed(true);
      }
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div style={styles.overlay}>
      <canvas ref={canvasRef} style={styles.canvas} />

      {/* Top Stage Indicator Pill */}
      <div style={styles.stagePill}>
        <span style={styles.stageDot} />
        <span>{stageName}</span>
      </div>

      {/* Skip Button (Bottom Right) */}
      <div style={styles.skipWrap}>
        <button
          onClick={handleFinish}
          style={styles.skipBtn}
          aria-label="Skip introduction animation"
        >
          <span>Skip Intro</span>
          <span style={{ fontSize: '1.05rem' }}>&raquo;</span>
        </button>
      </div>

      {/* Enter Conference CTA Overlay */}
      <div
        style={{
          ...styles.ctaOverlay,
          opacity: showEnterBtn ? 1 : 0,
          pointerEvents: showEnterBtn ? 'auto' : 'none',
          transform: showEnterBtn ? 'translateY(0)' : 'translateY(12px)',
        }}
      >
        <p style={styles.tagline}>Real-Time Multilingual Video Conferencing</p>
        <button onClick={handleFinish} style={styles.enterBtn}>
          <span>Enter VAAK</span>
          <span style={{ fontSize: '1.2rem' }}>&rarr;</span>
        </button>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 9999,
    backgroundColor: '#090809',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    userSelect: 'none',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  canvas: {
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    display: 'block',
  },
  stagePill: {
    position: 'absolute',
    top: '28px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 20,
    display: 'flex',
    alignItems: 'center',
    gap: '9px',
    padding: '7px 18px',
    borderRadius: '999px',
    backgroundColor: 'rgba(23, 16, 25, 0.85)',
    backdropFilter: 'blur(10px)',
    border: '1px solid rgba(162, 143, 165, 0.35)',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5)',
    fontSize: '0.76rem',
    fontWeight: 700,
    color: '#E8E2E8',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
  },
  stageDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#A28FA5',
    boxShadow: '0 0 8px #A28FA5',
  },
  ctaOverlay: {
    position: 'absolute',
    bottom: '48px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '14px',
    zIndex: 25,
    transition: 'opacity 0.6s ease, transform 0.6s ease',
  },
  tagline: {
    color: '#A28FA5',
    fontSize: '0.9rem',
    fontWeight: 500,
    letterSpacing: '0.04em',
    textShadow: '0 2px 8px rgba(0,0,0,0.8)',
  },
  enterBtn: {
    padding: '0.9rem 2.2rem',
    background: 'linear-gradient(135deg, #302034, #49334D)',
    color: '#E8E2E8',
    border: '1px solid rgba(162, 143, 165, 0.5)',
    borderRadius: '14px',
    fontWeight: 700,
    fontSize: '0.95rem',
    letterSpacing: '0.04em',
    cursor: 'pointer',
    boxShadow: '0 8px 25px rgba(0, 0, 0, 0.6), 0 0 15px rgba(162, 143, 165, 0.25)',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '10px',
    transition: 'all 0.2s ease',
  },
  skipWrap: {
    position: 'absolute',
    bottom: '24px',
    right: '24px',
    zIndex: 30,
  },
  skipBtn: {
    padding: '8px 16px',
    backgroundColor: 'rgba(23, 16, 25, 0.75)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(162, 143, 165, 0.3)',
    borderRadius: '10px',
    color: '#A28FA5',
    fontSize: '0.8rem',
    fontWeight: 600,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    transition: 'all 0.15s ease',
  },
};
