import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  useRoomContext,
} from '@livekit/components-react';
import { Track, RoomEvent } from 'livekit-client';

import { JoinScreen } from './JoinScreen';
import { VideoGrid } from './VideoGrid';
import { SubtitlePanel } from './SubtitlePanel';
import { useRoomSocket } from './useRoomSocket';
import { MicCaptureManager } from './micWorklet';
import { AudioQueue } from './audioQueue';
import { GoogleAuth } from './GoogleAuth';
import { LogoReveal } from './LogoReveal';

const CALL_SERVER_URL = import.meta.env.VITE_CALL_SERVER_URL || 'http://localhost:8000';

export default function App() {
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('vaak_user');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });

  const [authStage, setAuthStage] = useState(() => {
    try {
      return localStorage.getItem('vaak_user') ? 'intro' : 'auth';
    } catch (e) {
      return 'auth';
    }
  });

  const [session, setSession] = useState(null); // { roomId, participantId, name, lang, token, livekitUrl }
  const [mainCaptions, setMainCaptions] = useState([]);
  const [overlapCaptions, setOverlapCaptions] = useState([]);
  const [showDebug, setShowDebug] = useState(false);
  const [lastChunkDelayMs, setLastChunkDelayMs] = useState(null);
  const [micError, setMicError] = useState(null);

  const audioQueueRef = useRef(null);
  const micManagerRef = useRef(null);
  const liveKitStatsGetterRef = useRef(null);

  // Initialize AudioQueue with Audio Ducking wired (Bug 5 fix)
  useEffect(() => {
    const duckCallAudio = (targetVolume) => {
      document.querySelectorAll('audio').forEach((el) => {
        // Do not duck the translated speech playback itself
        if (el !== audioQueueRef.current?.currentAudio) {
          el.dataset.origVolume = el.dataset.origVolume || String(el.volume);
          el.volume = targetVolume;
        }
      });
    };

    audioQueueRef.current = new AudioQueue({
      onDuckStart: () => duckCallAudio(0.15),
      onDuckEnd: () => duckCallAudio(1.0),
    });

    return () => audioQueueRef.current?.clear();
  }, []);

  const handleTranslation = useCallback((msg) => {
    // Track chunk round-trip / processing delay (Feature 8)
    if (msg.ts_ms) {
      setLastChunkDelayMs(Math.max(0, Date.now() - msg.ts_ms));
    }

    if (msg.lane === 'overlap') {
      // Overlap lane limited to recent entries, trimmed to 2 lines in UI (Contract A4)
      setOverlapCaptions((prev) => [msg, ...prev].slice(0, 15));
    } else {
      setMainCaptions((prev) => [msg, ...prev].slice(0, 50));
    }

    // Play translated speech if audio_url provided and listener mode is audio
    if (msg.audio_url && msg.mode === 'audio') {
      audioQueueRef.current?.enqueue(msg.audio_url);
    }
  }, []);

  // Real WebRTC Stats getter (Bug 1 fix)
  const getLiveKitStats = useCallback(async () => {
    if (liveKitStatsGetterRef.current) {
      return await liveKitStatsGetterRef.current();
    }
    return null;
  }, []);

  const {
    connected: wsConnected,
    participants,
    activeSpeaker,
    mode,
    lastNetStats,
    setLanguage,
  } = useRoomSocket({
    callServerUrl: CALL_SERVER_URL,
    roomId: session?.roomId,
    participantId: session?.participantId,
    name: session?.name,
    lang: session?.lang,
    onTranslation: handleTranslation,
    getLiveKitStats,
  });

  // Start Mic Audio Streaming to Call Server on join with error reporting and auto-reconnect (Bug 6 & 7)
  useEffect(() => {
    if (!session) return;

    setMicError(null);
    const wsProto = CALL_SERVER_URL.startsWith('https') ? 'wss' : 'ws';
    const host = CALL_SERVER_URL.replace(/^https?:\/\//, '');
    const audioWsUrl = `${wsProto}://${host}/ws/audio/${session.roomId}/${session.participantId}`;

    const micManager = new MicCaptureManager(audioWsUrl, {
      onError: (errMsg) => {
        setMicError(errMsg);
      },
    });
    micManagerRef.current = micManager;

    micManager.start().catch((err) => {
      console.warn('Microphone capture initialization failed:', err);
      setMicError('Microphone stream error. Check permissions.');
    });

    return () => {
      micManager.stop();
      micManagerRef.current = null;
    };
  }, [session]);

  const handleJoin = async ({ roomId, participantId, name, lang }) => {
    const res = await fetch(`${CALL_SERVER_URL}/v1/rooms/${roomId}/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ participant_id: participantId, name, lang }),
    });

    if (!res.ok) {
      throw new Error(`Failed to join room: ${res.statusText}`);
    }

    const data = await res.json();
    setSession({
      roomId,
      participantId,
      name,
      lang,
      token: data.livekit_token,
      livekitUrl: data.livekit_url,
    });
  };

  const handleLeave = () => {
    micManagerRef.current?.stop();
    audioQueueRef.current?.clear();
    setSession(null);
    setMainCaptions([]);
    setOverlapCaptions([]);
    setLastChunkDelayMs(null);
    setMicError(null);
  };

  const handleLangChange = (e) => {
    const newLang = e.target.value;
    setSession((prev) => ({ ...prev, lang: newLang }));
    setLanguage(newLang);
  };

  if (authStage === 'auth') {
    return (
      <GoogleAuth
        onAuthenticated={(u) => {
          setCurrentUser(u);
          setAuthStage('intro');
        }}
      />
    );
  }

  if (authStage === 'intro') {
    return (
      <LogoReveal
        onComplete={() => setAuthStage('join')}
      />
    );
  }

  if (!session) {
    return (
      <JoinScreen
        onJoin={handleJoin}
        user={currentUser}
        onReplayIntro={() => setAuthStage('intro')}
        onSignOut={() => {
          localStorage.removeItem('vaak_user');
          setCurrentUser(null);
          setAuthStage('auth');
        }}
      />
    );
  }

  const isAudioMode = mode.mode === 'audio';

  return (
    <LiveKitRoom
      token={session.token}
      serverUrl={session.livekitUrl}
      connect={true}
      audio={true}
      video={true}
      options={{
        adaptiveStream: true,
        dynacast: true,
      }}
      className="conference-shell"
    >
      {/* LiveKit Controller for real getStats() & Mute Sync */}
      <LiveKitController
        onRegisterStatsGetter={(getter) => {
          liveKitStatsGetterRef.current = getter;
        }}
        onMuteChange={(isMuted) => {
          // Bug 2 fix: sync LiveKit mute button with translation audio capture
          micManagerRef.current?.setMuted(isMuted);
        }}
      />

      {/* Mic Error Banner */}
      {micError && (
        <div style={{ backgroundColor: '#ef4444', color: '#fff', padding: '6px 12px', fontSize: '12px', textAlign: 'center', zIndex: 100 }}>
          ⚠️ {micError}
        </div>
      )}

      {/* Top Navigation Bar */}
      <header className="conf-header">
        <div className="header-left">
          <img
            src="/vaak_logo.png"
            alt="VAAK"
            style={{ height: '30px', width: 'auto', objectFit: 'contain', marginRight: '8px' }}
          />
          <h2 className="room-title">Room: {session.roomId}</h2>
          <span className="participant-count-badge">
            👥 {participants.length || 1} participant{participants.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="header-center">
          {/* Mode Badge based on network evaluation */}
          <div className={`mode-badge ${isAudioMode ? 'badge-audio' : 'badge-sub'}`}>
            <span className="mode-dot"></span>
            <span className="mode-text">
              {isAudioMode ? 'Audio Mode' : 'Subtitle Mode (Adaptive)'}
            </span>
            <span className="mode-reason">({mode.reason || 'monitoring'})</span>
          </div>
        </div>

        <div className="header-right">
          <label className="lang-label">
            Translate into:
            <select
              value={session.lang}
              onChange={handleLangChange}
              className="lang-select"
            >
              <option value="en">English</option>
              <option value="hi">Hindi (हिंदी)</option>
              <option value="kn">Kannada (ಕನ್ನಡ)</option>
              <option value="ta">Tamil (தமிழ்)</option>
              <option value="te">Telugu (తెలుగు)</option>
              <option value="ml">Malayalam (മലയാളം)</option>
              <option value="mr">Marathi (मराठी)</option>
            </select>
          </label>
          <button
            onClick={() => setShowDebug(!showDebug)}
            className="btn-debug-toggle"
          >
            {showDebug ? 'Hide Stats' : 'QoS Stats'}
          </button>
        </div>
      </header>

      {/* Main Conference Content: Video Grid + Subtitles */}
      <div className="conf-body">
        <main className="conf-stage">
          <VideoGrid
            activeSpeaker={activeSpeaker}
            participantsList={participants}
          />

          {/* Debug panel with chunk delay and real WebRTC QoS */}
          {showDebug && lastNetStats && (
            <div className="debug-card">
              <h4>Real-Time QoS Network Diagnostics</h4>
              <div className="debug-grid">
                <div>RTT: <strong>{lastNetStats.rtt_ms} ms</strong></div>
                <div>Packet Loss: <strong>{lastNetStats.packet_loss_pct}%</strong></div>
                <div>Bitrate: <strong>{lastNetStats.bitrate_kbps} kbps</strong></div>
                <div>Jitter: <strong>{lastNetStats.jitter_ms} ms</strong></div>
                <div>Current Mode: <strong style={{ textTransform: 'uppercase' }}>{mode.mode}</strong></div>
                <div>Chunk Delay: <strong>{lastChunkDelayMs !== null ? `${lastChunkDelayMs} ms` : 'Measuring...'}</strong></div>
              </div>
            </div>
          )}
        </main>

        <aside className="conf-sidebar">
          <SubtitlePanel
            mainCaptions={mainCaptions}
            overlapCaptions={overlapCaptions}
          />
        </aside>
      </div>

      {/* Control Bar */}
      <footer className="conf-footer">
        <div className="controls-group">
          <TrackToggle source={Track.Source.Microphone} className="control-btn" />
          <TrackToggle source={Track.Source.Camera} className="control-btn" />
          <button onClick={handleLeave} className="control-btn btn-leave">
            Leave Meeting
          </button>
        </div>
      </footer>

      {/* Audio playback from LiveKit WebRTC */}
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

/**
 * Controller inside LiveKitRoom to access real RTCPeerConnection stats & mute events
 */
function LiveKitController({ onRegisterStatsGetter, onMuteChange }) {
  const room = useRoomContext();
  const lastBytesRef = useRef(0);
  const lastTimeRef = useRef(Date.now());

  useEffect(() => {
    if (!room) return;

    // 1. Register stats getter
    const getStats = async () => {
      try {
        const pc = room.engine?.client?.pc;
        if (!pc || !pc.getStats) return null;

        const reports = await pc.getStats();
        let rtt = 45;
        let packetLossPct = 0.0;
        let bitrateKbps = 850;
        let jitterMs = 8;

        reports.forEach((report) => {
          // RTT from selected candidate-pair
          if (report.type === 'candidate-pair' && report.state === 'succeeded') {
            if (typeof report.currentRoundTripTime === 'number') {
              rtt = Math.round(report.currentRoundTripTime * 1000);
            }
          }

          // Packet Loss, Jitter & Bitrate from inbound-rtp
          if (report.type === 'inbound-rtp' && (report.kind === 'video' || report.kind === 'audio')) {
            if (report.packetsLost && report.packetsReceived) {
              const totalPackets = report.packetsLost + report.packetsReceived;
              if (totalPackets > 0) {
                packetLossPct = parseFloat(((report.packetsLost / totalPackets) * 100).toFixed(1));
              }
            }
            if (typeof report.jitter === 'number') {
              jitterMs = Math.round(report.jitter * 1000);
            }
            if (typeof report.bytesReceived === 'number') {
              const now = Date.now();
              const dt = (now - lastTimeRef.current) / 1000;
              if (dt > 0.5) {
                const deltaBytes = report.bytesReceived - lastBytesRef.current;
                bitrateKbps = Math.max(0, Math.round((deltaBytes * 8) / (dt * 1000)));
                lastBytesRef.current = report.bytesReceived;
                lastTimeRef.current = now;
              }
            }
          }
        });

        return {
          rtt_ms: rtt,
          packet_loss_pct: packetLossPct,
          bitrate_kbps: bitrateKbps,
          jitter_ms: jitterMs,
        };
      } catch (e) {
        return null;
      }
    };

    onRegisterStatsGetter(getStats);

    // 2. Mute sync listener (Bug 2 fix)
    const checkMuteState = () => {
      const isMuted = !room.localParticipant.isMicrophoneEnabled;
      onMuteChange(isMuted);
    };

    room.on(RoomEvent.TrackMuted, checkMuteState);
    room.on(RoomEvent.TrackUnmuted, checkMuteState);
    room.on(RoomEvent.LocalTrackPublished, checkMuteState);
    room.on(RoomEvent.LocalTrackUnpublished, checkMuteState);

    // Initial check
    checkMuteState();

    return () => {
      room.off(RoomEvent.TrackMuted, checkMuteState);
      room.off(RoomEvent.TrackUnmuted, checkMuteState);
      room.off(RoomEvent.LocalTrackPublished, checkMuteState);
      room.off(RoomEvent.LocalTrackUnpublished, checkMuteState);
    };
  }, [room, onRegisterStatsGetter, onMuteChange]);

  return null;
}
