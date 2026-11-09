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
import { createStatsTracker } from './netStats';
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
  const [simulatePoor, setSimulatePoor] = useState(false);
  const [lastChunkDelayMs, setLastChunkDelayMs] = useState(null);
  const [micError, setMicError] = useState(null);

  const audioQueueRef = useRef(null);
  const micManagerRef = useRef(null);
  const liveKitStatsGetterRef = useRef(null);
  const mutedRef = useRef(false); // last known LiveKit mic state, so a new MicCaptureManager starts in sync

  // AudioQueue with ducking: call audio goes down to 15% while translated speech plays,
  // and each element goes back to ITS OWN original volume afterwards.
  useEffect(() => {
    const duckCallAudio = (duck) => {
      document.querySelectorAll('audio').forEach((el) => {
        if (el === audioQueueRef.current?.currentAudio) return; // never duck the translated speech itself
        if (duck) {
          if (el.dataset.origVolume === undefined) el.dataset.origVolume = String(el.volume);
          el.volume = 0.15;
        } else if (el.dataset.origVolume !== undefined) {
          el.volume = Number(el.dataset.origVolume);
          delete el.dataset.origVolume;
        }
      });
    };

    audioQueueRef.current = new AudioQueue({
      onDuckStart: () => duckCallAudio(true),
      onDuckEnd: () => duckCallAudio(false),
    });

    return () => audioQueueRef.current?.clear();
  }, []);

  const handleTranslation = useCallback((msg) => {
    // Track chunk round-trip / processing delay
    if (msg.ts_ms) {
      setLastChunkDelayMs(Math.max(0, Date.now() - msg.ts_ms));
    }

    if (msg.lane === 'overlap') {
      // Overlap lane keeps recent entries; SubtitlePanel shows the latest line of up to 2 talkers (Contract A4)
      setOverlapCaptions((prev) => [msg, ...prev].slice(0, 15));
    } else {
      setMainCaptions((prev) => [msg, ...prev].slice(0, 50));
    }

    // Play translated speech if audio_url provided and listener mode is audio
    if (msg.audio_url && msg.mode === 'audio') {
      audioQueueRef.current?.enqueue(msg.audio_url);
    }
  }, []);

  // Stable callbacks: LiveKitController's effect depends on them. If they changed on every render
  // (e.g. each incoming caption), the stats tracker would be re-created and lose its history.
  const registerStatsGetter = useCallback((getter) => {
    liveKitStatsGetterRef.current = getter;
  }, []);

  const handleMuteChange = useCallback((isMuted) => {
    mutedRef.current = isMuted;
    micManagerRef.current?.setMuted(isMuted);
  }, []);

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
    simulatePoor,
  });

  // Start mic streaming to the call server on join.
  // Depends only on room + participant: changing the translation language (which updates `session`)
  // must NOT restart the microphone.
  useEffect(() => {
    if (!session?.roomId || !session?.participantId) return;

    setMicError(null);
    const wsProto = CALL_SERVER_URL.startsWith('https') ? 'wss' : 'ws';
    const host = CALL_SERVER_URL.replace(/^https?:\/\//, '');
    const audioWsUrl = `${wsProto}://${host}/ws/audio/${session.roomId}/${session.participantId}`;

    const micManager = new MicCaptureManager(audioWsUrl, {
      onError: (errMsg) => {
        setMicError(errMsg);
      },
    });
    micManager.setMuted(mutedRef.current);
    micManagerRef.current = micManager;

    micManager.start().catch((err) => {
      console.warn('Microphone capture initialization failed:', err);
      setMicError('Microphone stream error. Check permissions.');
    });

    return () => {
      micManager.stop();
      micManagerRef.current = null;
    };
  }, [session?.roomId, session?.participantId]);

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
    setSimulatePoor(false);
    mutedRef.current = false;
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
      {/* LiveKit Controller: real getStats() + mute sync */}
      <LiveKitController
        onRegisterStatsGetter={registerStatsGetter}
        onMuteChange={handleMuteChange}
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

          {/* QoS panel: real WebRTC stats, chunk delay, and the simulate-poor-network switch */}
          {showDebug && (
            <div className="debug-card">
              <h4>Real-Time QoS Network Diagnostics</h4>

              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', marginBottom: '8px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={simulatePoor}
                  onChange={(e) => setSimulatePoor(e.target.checked)}
                />
                Simulate poor network (demo: forces Subtitle Mode within ~6 s)
              </label>

              {lastNetStats ? (
                <div className="debug-grid">
                  <div>RTT: <strong>{lastNetStats.rtt_ms} ms</strong></div>
                  <div>Packet Loss: <strong>{lastNetStats.packet_loss_pct}%</strong></div>
                  <div>Bitrate: <strong>{lastNetStats.bitrate_kbps} kbps</strong></div>
                  <div>Jitter: <strong>{lastNetStats.jitter_ms} ms</strong></div>
                  <div>Current Mode: <strong style={{ textTransform: 'uppercase' }}>{mode.mode}</strong></div>
                  <div>Chunk Delay: <strong>{lastChunkDelayMs !== null ? `${lastChunkDelayMs} ms` : 'Measuring...'}</strong></div>
                  {lastNetStats.simulated && <div style={{ color: '#f59e0b' }}>⚠ simulated values</div>}
                </div>
              ) : (
                <p style={{ fontSize: '12px', opacity: 0.8 }}>
                  Waiting for WebRTC statistics… (needs about 2 seconds of an established call)
                </p>
              )}
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
 * Find the objects that can run getStats() for the two WebRTC connections of the call
 * (publisher = what we send, subscriber = what we receive).
 * The internal layout differs between livekit-client versions, so several places are tried.
 * ALWAYS returns [publisherSource, subscriberSource]; a missing one is null (keeps stream keys stable).
 */
function findStatsSources(room) {
  const engine = room?.engine;
  const pcm = engine?.pcManager;                       // livekit-client >= 2.x
  const candidates = [
    pcm?.publisher ?? engine?.publisher,               // older versions: engine.publisher
    pcm?.subscriber ?? engine?.subscriber,
  ];

  return candidates.map((t) => {
    if (!t) return null;
    const pc = t.pc ?? t._pc;
    if (pc && typeof pc.getStats === 'function') return pc;   // raw RTCPeerConnection
    if (typeof t.getStats === 'function') return t;           // or the transport wrapper itself
    return null;
  });
}

/**
 * Controller inside LiveKitRoom to access real RTCPeerConnection stats & mute events
 */
function LiveKitController({ onRegisterStatsGetter, onMuteChange }) {
  const room = useRoomContext();

  useEffect(() => {
    if (!room) return;

    // 1. Real stats: measured per 2-second window by netStats.js
    const tracker = createStatsTracker();
    let warned = false;

    const getStats = async () => {
      const sources = findStatsSources(room);
      if (!sources[0] && !sources[1]) {
        if (!warned) {
          warned = true;
          console.warn(
            '[VAAK] No RTCPeerConnection found on room.engine. Inspect it in the console: ' +
            'Object.keys(room.engine) and Object.keys(room.engine.pcManager || {}) ' +
            'and update findStatsSources() in App.jsx.'
          );
        }
        return null;
      }
      const reports = await Promise.all(
        sources.map((s) => (s ? s.getStats().catch(() => null) : Promise.resolve(null)))
      );
      return tracker(reports); // null until it has two samples and a round-trip time
    };

    onRegisterStatsGetter(getStats);

    // 2. Mute sync: muting in LiveKit stops translation audio capture
    const checkMuteState = () => {
      const isMuted = !room.localParticipant.isMicrophoneEnabled;
      onMuteChange(isMuted);
    };

    room.on(RoomEvent.TrackMuted, checkMuteState);
    room.on(RoomEvent.TrackUnmuted, checkMuteState);
    room.on(RoomEvent.LocalTrackPublished, checkMuteState);
    room.on(RoomEvent.LocalTrackUnpublished, checkMuteState);

    checkMuteState(); // initial

    return () => {
      room.off(RoomEvent.TrackMuted, checkMuteState);
      room.off(RoomEvent.TrackUnmuted, checkMuteState);
      room.off(RoomEvent.LocalTrackPublished, checkMuteState);
      room.off(RoomEvent.LocalTrackUnpublished, checkMuteState);
    };
  }, [room, onRegisterStatsGetter, onMuteChange]);

  return null;
}
