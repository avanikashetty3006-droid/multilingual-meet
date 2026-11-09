import React, { useEffect, useRef, useState } from 'react';

export function LogoReveal({ onComplete }) {
  const canvasRef = useRef(null);
  const [stageName, setStageName] = useState('Global Network');
  const [showFinalLogo, setShowFinalLogo] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);

  // Vaak Brand Palette
  const PALETTE = {
    dark: '#3E2522',
    brown: '#8C6E63',
    gold: '#D3A376',
    peach: '#FFE0B2',
    cream: '#FFF2DF',
  };

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

    // Approximate continent clusters for the centered world map (lon/lat normalized -1..1)
    const worldClusters = [
      // North America
      { cx: -0.55, cy: -0.25, count: 180, spreadX: 0.18, spreadY: 0.15 },
      // South America
      { cx: -0.38, cy: 0.25, count: 130, spreadX: 0.10, spreadY: 0.20 },
      // Europe
      { cx: 0.05, cy: -0.28, count: 140, spreadX: 0.10, spreadY: 0.10 },
      // Africa
      { cx: 0.08, cy: 0.12, count: 170, spreadX: 0.12, spreadY: 0.22 },
      // Asia / Eurasia
      { cx: 0.42, cy: -0.20, count: 260, spreadX: 0.24, spreadY: 0.16 },
      // India (Focal hub)
      { cx: 0.32, cy: -0.02, count: 150, spreadX: 0.07, spreadY: 0.09 },
      // East Asia / Japan
      { cx: 0.65, cy: -0.15, count: 100, spreadX: 0.09, spreadY: 0.12 },
      // Oceania / Australia
      { cx: 0.60, cy: 0.35, count: 120, spreadX: 0.12, spreadY: 0.10 },
    ];

    // Major communication arcs between hubs
    const commHubs = [
      { x: -0.55, y: -0.25, label: 'Americas' },
      { x: 0.05, y: -0.28, label: 'Europe' },
      { x: 0.08, y: 0.12, label: 'Africa' },
      { x: 0.32, y: -0.02, label: 'India' },
      { x: 0.55, y: -0.20, label: 'Asia' },
      { x: 0.60, y: 0.35, label: 'Oceania' },
    ];

    const particleColors = [PALETTE.dark, PALETTE.brown, PALETTE.gold, PALETTE.peach];

    // Generate Particles
    const particles = [];
    worldClusters.forEach((cluster) => {
      for (let i = 0; i < cluster.count; i++) {
        // Gaussian-like scatter
        const rx = (Math.random() + Math.random() - 1) * cluster.spreadX;
        const ry = (Math.random() + Math.random() - 1) * cluster.spreadY;
        const targetWorldX = width / 2 + (cluster.cx + rx) * (width * 0.42);
        const targetWorldY = height / 2 + (cluster.cy + ry) * (height * 0.45);

        // Logo Target Coordinates (forming video cam, speech bubbles & Vaak ribbon)
        const logoTheta = Math.random() * Math.PI * 2;
        const logoDist = Math.pow(Math.random(), 0.5) * 140;
        const targetLogoX = width / 2 + Math.cos(logoTheta) * logoDist;
        const targetLogoY = height / 2 + Math.sin(logoTheta) * (logoDist * 0.7) - 20;

        particles.push({
          x: targetWorldX + (Math.random() - 0.5) * 30,
          y: targetWorldY + (Math.random() - 0.5) * 30,
          originX: targetWorldX,
          originY: targetWorldY,
          targetLogoX,
          targetLogoY,
          vx: 0,
          vy: 0,
          size: Math.random() * 2.2 + 1.2,
          baseSize: Math.random() * 2.2 + 1.2,
          color: particleColors[Math.floor(Math.random() * particleColors.length)],
          shimmerSpeed: 0.02 + Math.random() * 0.04,
          shimmerOffset: Math.random() * Math.PI * 2,
          connectedTo: Math.floor(Math.random() * commHubs.length),
        });
      }
    });

    const startTime = performance.now();
    let currentStage = 1;

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;

      // Stage progression timeline:
      // 0 - 2200ms: Stage 1 - Centered World Map
      // 2200 - 4500ms: Stage 2 - Dotted Transformation & Interconnected Network Flow
      // 4500 - 6800ms: Stage 3 - Gathering Motion (Magnetic attraction to center)
      // 6800 - 8500ms: Stage 4 - Logo Formation
      // 8500ms+: Stage 5 - Final Reveal & Tagline
      if (elapsed < 2200) {
        if (currentStage !== 1) {
          currentStage = 1;
          setStageName('Connecting Continents');
        }
      } else if (elapsed < 4500) {
        if (currentStage !== 2) {
          currentStage = 2;
          setStageName('Global Language Network');
        }
      } else if (elapsed < 6800) {
        if (currentStage !== 3) {
          currentStage = 3;
          setStageName('Convergence');
        }
      } else if (elapsed < 8500) {
        if (currentStage !== 4) {
          currentStage = 4;
          setStageName('Logo Assembly');
        }
      } else {
        if (currentStage !== 5) {
          currentStage = 5;
          setStageName('VAAK Revealed');
          setShowFinalLogo(true);
        }
      }

      // Clear Canvas with warm background tone
      ctx.fillStyle = PALETTE.cream;
      ctx.fillRect(0, 0, width, height);

      // Ambient radial gradient behind map/logo
      const ambientGrad = ctx.createRadialGradient(
        width / 2,
        height / 2,
        40,
        width / 2,
        height / 2,
        width * 0.55
      );
      ambientGrad.addColorStop(0, '#FFE0B244');
      ambientGrad.addColorStop(0.6, '#D3A37618');
      ambientGrad.addColorStop(1, '#FFF2DF00');
      ctx.fillStyle = ambientGrad;
      ctx.fillRect(0, 0, width, height);

      // Render Communication Arcs (Stage 1 & 2)
      if (elapsed < 6000) {
        const arcProgress = Math.min(1, elapsed / 2500);
        const arcAlpha =
          elapsed < 4500
            ? arcProgress * 0.25
            : Math.max(0, (6000 - elapsed) / 1500) * 0.25;

        ctx.lineWidth = 1;
        commHubs.forEach((hubA, idx) => {
          const hubB = commHubs[(idx + 2) % commHubs.length];
          const x1 = width / 2 + hubA.x * (width * 0.42);
          const y1 = height / 2 + hubA.y * (height * 0.45);
          const x2 = width / 2 + hubB.x * (width * 0.42);
          const y2 = height / 2 + hubB.y * (height * 0.45);

          // Quadratic curve arc
          const midX = (x1 + x2) / 2;
          const midY = (y1 + y2) / 2 - 40;

          ctx.beginPath();
          ctx.strokeStyle = PALETTE.gold;
          ctx.globalAlpha = arcAlpha;
          ctx.moveTo(x1, y1);
          ctx.quadraticCurveTo(midX, midY, x2, y2);
          ctx.stroke();

          // Flowing pulse particle along the arc
          const pulseT = (elapsed * 0.0006 + idx * 0.25) % 1;
          const px =
            (1 - pulseT) * (1 - pulseT) * x1 +
            2 * (1 - pulseT) * pulseT * midX +
            pulseT * pulseT * x2;
          const py =
            (1 - pulseT) * (1 - pulseT) * y1 +
            2 * (1 - pulseT) * pulseT * midY +
            pulseT * pulseT * y2;

          ctx.fillStyle = PALETTE.dark;
          ctx.globalAlpha = arcAlpha * 2.5;
          ctx.beginPath();
          ctx.arc(px, py, 2.5, 0, Math.PI * 2);
          ctx.fill();
        });
        ctx.globalAlpha = 1.0;
      }

      // Update and Draw Particles
      particles.forEach((p) => {
        if (elapsed < 2200) {
          // Stage 1: gentle float around world map
          const driftX = Math.sin(elapsed * 0.0015 + p.shimmerOffset) * 2;
          const driftY = Math.cos(elapsed * 0.0015 + p.shimmerOffset) * 2;
          p.x = p.originX + driftX;
          p.y = p.originY + driftY;
          p.size = p.baseSize;
        } else if (elapsed < 4500) {
          // Stage 2: Shimmering digital network flow
          const wave = Math.sin(elapsed * p.shimmerSpeed + p.shimmerOffset);
          p.size = p.baseSize * (1 + 0.45 * wave);
          p.x += Math.sin(elapsed * 0.002 + p.shimmerOffset) * 0.8;
          p.y += Math.cos(elapsed * 0.002 + p.shimmerOffset) * 0.8;
        } else if (elapsed < 6800) {
          // Stage 3: Gathering motion toward center (Magnetic force)
          const gatherT = (elapsed - 4500) / 2300;
          const ease = Math.min(1, gatherT * gatherT);

          const angle = Math.atan2(p.y - height / 2, p.x - width / 2) + 0.06;
          const dist = Math.hypot(p.x - width / 2, p.y - height / 2);
          const targetDist = dist * (1 - ease * 0.08);

          p.x = width / 2 + Math.cos(angle) * targetDist;
          p.y = height / 2 + Math.sin(angle) * targetDist;
          p.size = p.baseSize * (1.1 - ease * 0.3);
        } else if (elapsed < 8500) {
          // Stage 4: Form the VAAK Logo
          p.x += (p.targetLogoX - p.x) * 0.12;
          p.y += (p.targetLogoY - p.y) * 0.12;
          p.size = p.baseSize * 1.1;
        } else {
          // Stage 5: Dissolve into glowing halo around final logo
          const dissolveT = Math.min(1, (elapsed - 8500) / 1200);
          const floatAngle = p.shimmerOffset + elapsed * 0.0005;
          p.x += Math.cos(floatAngle) * 0.4;
          p.y += Math.sin(floatAngle) * 0.4;
          ctx.globalAlpha = Math.max(0, 1 - dissolveT * 0.85);
        }

        // Draw individual particle
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0.8, p.size), 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1.0;
      });

      if (elapsed < 11000) {
        animationFrameId = requestAnimationFrame(animate);
      } else {
        setIsCompleted(true);
      }
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  const handleSkipOrProceed = () => {
    setIsCompleted(true);
    setShowFinalLogo(true);
    if (onComplete) onComplete();
  };

  return (
    <div style={styles.overlay}>
      <canvas ref={canvasRef} style={styles.canvas} />

      {/* Stage Indicator Pill */}
      <div style={styles.stagePill}>
        <span style={styles.stageDot} />
        <span>{stageName}</span>
      </div>

      {/* Final Logo & Tagline Reveal Overlay */}
      <div
        style={{
          ...styles.logoOverlay,
          opacity: showFinalLogo ? 1 : 0,
          transform: showFinalLogo ? 'scale(1)' : 'scale(0.96)',
          pointerEvents: showFinalLogo ? 'auto' : 'none',
        }}
      >
        <div style={styles.logoCard}>
          <div style={styles.logoImageWrap}>
            <img
              src="/vaak_logo.png"
              alt="VAAK Logo"
              style={styles.logoImage}
              onError={(e) => {
                e.currentTarget.src = './src/assets/vaak_logo.png';
              }}
            />
          </div>

          <button onClick={handleSkipOrProceed} style={styles.enterBtn}>
            <span>Enter Video Conference</span>
            <span style={{ fontSize: '1.1rem' }}>&rarr;</span>
          </button>
        </div>
      </div>

      {/* Skip Controls (Bottom Right) */}
      <div style={styles.skipWrap}>
        <button onClick={handleSkipOrProceed} style={styles.skipBtn}>
          <span>Skip Animation</span>
          <span>&raquo;</span>
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
    backgroundColor: '#FFF2DF',
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
    top: '24px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 20,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '6px 16px',
    borderRadius: '999px',
    backgroundColor: 'rgba(255, 255, 255, 0.85)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(211, 163, 118, 0.6)',
    boxShadow: '0 4px 12px rgba(62, 37, 34, 0.08)',
    fontSize: '0.75rem',
    fontWeight: 700,
    color: '#3E2522',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  stageDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#D3A376',
  },
  logoOverlay: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
    transition: 'opacity 0.8s ease-out, transform 0.8s ease-out',
  },
  logoCard: {
    padding: '2rem',
    maxWidth: '480px',
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
  },
  logoImageWrap: {
    position: 'relative',
    marginBottom: '1.75rem',
  },
  logoImage: {
    width: '340px',
    maxWidth: '90vw',
    height: 'auto',
    objectFit: 'contain',
    filter: 'drop-shadow(0 15px 30px rgba(62, 37, 34, 0.2))',
  },
  enterBtn: {
    padding: '0.85rem 1.75rem',
    backgroundColor: '#3E2522',
    color: '#FFF2DF',
    border: 'none',
    borderRadius: '12px',
    fontWeight: 700,
    fontSize: '0.9rem',
    letterSpacing: '0.02em',
    cursor: 'pointer',
    boxShadow: '0 6px 20px rgba(62, 37, 34, 0.25)',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '10px',
    transition: 'all 0.2s ease',
  },
  skipWrap: {
    position: 'absolute',
    bottom: '24px',
    right: '24px',
    zIndex: 20,
  },
  skipBtn: {
    padding: '8px 16px',
    backgroundColor: 'rgba(255, 255, 255, 0.85)',
    border: '1px solid rgba(211, 163, 118, 0.6)',
    borderRadius: '8px',
    color: '#3E2522',
    fontSize: '0.78rem',
    fontWeight: 700,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)',
  },
};
