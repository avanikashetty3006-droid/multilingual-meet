import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  useRoomContext,
} from '@livekit/components-react';
import { Track, RoomEvent } from 'livekit-client';
import { Copy, Check, PhoneOff, Activity, Globe, ShieldAlert } from 'lucide-react';

import { VideoGrid } from '../VideoGrid';
import { SubtitlePanel } from '../SubtitlePanel';
import { useRoomSocket } from '../useRoomSocket';
import { MicCaptureManager } from '../micWorklet';
import { AudioQueue } from '../audioQueue';
import { createStatsTracker } from '../netStats';
import { api } from '../api/client';

const CALL_SERVER_URL = import.meta.env.VITE_CALL_SERVER_URL || 'http://localhost:8000';

export function ConferenceView({ session, onLeave }) {
  const [currentLang, setCurrentLang] = useState(session.lang || 'hi');
  const [mainCaptions, setMainCaptions] = useState([]);
  const [overlapCaptions, setOverlapCaptions] = useState([]);
  const [showDebug, setShowDebug] = useState(false);
  const [simulatePoor, setSimulatePoor] = useState(false);
  const [lastChunkDelayMs, setLastChunkDelayMs] = useState(null);
  const [micError, setMicError] = useState(null);
  const [copiedLink, setCopiedLink] = useState(false);

  const audioQueueRef = useRef(null);
  const micManagerRef = useRef(null);
  const liveKitStatsGetterRef = useRef(null);
  const mutedRef = useRef(!session.initialMic);

  // AudioQueue with ducking
  useEffect(() => {
    const duckCallAudio = (duck) => {
      document.querySelectorAll('audio').forEach((el) => {
        if (el === audioQueueRef.current?.currentAudio) return;
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
    if (msg.ts_ms) {
      setLastChunkDelayMs(Math.max(0, Date.now() - msg.ts_ms));
    }

    if (msg.lane === 'overlap') {
      setOverlapCaptions((prev) => [msg, ...prev].slice(0, 15));
    } else {
      setMainCaptions((prev) => [msg, ...prev].slice(0, 50));
    }

    if (msg.audio_url && msg.mode === 'audio') {
      audioQueueRef.current?.enqueue(msg.audio_url);
    }
  }, []);

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
    roomId: session.roomId,
    participantId: session.participantId,
    name: session.name,
    lang: currentLang,
    onTranslation: handleTranslation,
    getLiveKitStats,
    simulatePoor,
  });

  // Start mic streaming to Call Server
  useEffect(() => {
    if (!session.roomId || !session.participantId) return;

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
  }, [session.roomId, session.participantId]);

  const handleLangChange = (e) => {
    const newLang = e.target.value;
    setCurrentLang(newLang);
    setLanguage(newLang);
  };

  const handleCopyMeetingLink = () => {
    const url = `${window.location.origin}/m/${session.roomId}`;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleEndMeetingForAll = async () => {
    if (confirm('Are you sure you want to end this meeting for all participants?')) {
      try {
        await api.meetings.end(session.roomId);
      } catch (e) {
        console.warn('Failed to end meeting on server:', e);
      }
      handleLeaveCall();
    }
  };

  const handleLeaveCall = () => {
    micManagerRef.current?.stop();
    audioQueueRef.current?.clear();
    if (onLeave) onLeave();
  };

  const isAudioMode = mode.mode === 'audio';

  return (
    <LiveKitRoom
      token={session.token}
      serverUrl={session.livekitUrl}
      connect={true}
      audio={session.initialMic}
      video={session.initialCam}
      options={{
        adaptiveStream: true,
        dynacast: true,
      }}
      className="conference-shell"
    >
      <LiveKitController
        onRegisterStatsGetter={registerStatsGetter}
        onMuteChange={handleMuteChange}
      />

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
            style={{ height: '28px', width: 'auto', objectFit: 'contain' }}
            onError={(e) => {
              e.currentTarget.style.display = 'none';
            }}
          />
          <h2 className="room-title">Room: {session.roomId}</h2>
          <span className="participant-count-badge">
            👥 {participants.length || 1} participant{participants.length !== 1 ? 's' : ''}
          </span>
          <button
            onClick={handleCopyMeetingLink}
            className="btn-outline"
            style={{ padding: '3px 8px', fontSize: '0.75rem' }}
            title="Copy meeting link"
          >
            {copiedLink ? <Check size={13} color="var(--status-online)" /> : <Copy size={13} />}
            <span>{copiedLink ? 'Copied' : 'Share Link'}</span>
          </button>
        </div>

        <div className="header-center">
          <div className={`mode-badge ${isAudioMode ? 'badge-audio' : 'badge-sub'}`}>
            <span className="mode-dot"></span>
            <span className="mode-text">
              {isAudioMode ? 'Audio Mode' : 'Subtitle Mode (Adaptive)'}
            </span>
            <span className="mode-reason">({mode.reason || 'monitoring'})</span>
          </div>
        </div>

        <div className="header-right">
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: 'var(--vaak-muted-lilac)' }}>
            <Globe size={14} />
            <span>Listening:</span>
            <select
              value={currentLang}
              onChange={handleLangChange}
              className="select-custom"
              style={{ padding: '4px 8px', fontSize: '0.8rem', backgroundColor: 'var(--vaak-dark-eggplant)' }}
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
            className="btn-outline"
            style={{ padding: '4px 10px', fontSize: '0.78rem' }}
          >
            <Activity size={13} />
            <span>{showDebug ? 'Hide QoS' : 'QoS Stats'}</span>
          </button>
        </div>
      </header>

      {/* Main Conference Content */}
      <div className="conf-body">
        <main className="conf-stage">
          <VideoGrid
            activeSpeaker={activeSpeaker}
            participantsList={participants}
          />

          {showDebug && (
            <div className="debug-card">
              <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '8px', color: 'var(--vaak-warm-white)' }}>
                Real-Time QoS Network Diagnostics
              </h4>

              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', marginBottom: '8px', cursor: 'pointer', color: 'var(--vaak-muted-lilac)' }}>
                <input
                  type="checkbox"
                  checked={simulatePoor}
                  onChange={(e) => setSimulatePoor(e.target.checked)}
                />
                Simulate poor network (forces Subtitle Mode in ~6s)
              </label>

              {lastNetStats ? (
                <div className="debug-grid">
                  <div>RTT: <strong>{lastNetStats.rtt_ms} ms</strong></div>
                  <div>Loss: <strong>{lastNetStats.packet_loss_pct}%</strong></div>
                  <div>Bitrate: <strong>{lastNetStats.bitrate_kbps} kbps</strong></div>
                  <div>Jitter: <strong>{lastNetStats.jitter_ms} ms</strong></div>
                  <div>Mode: <strong style={{ textTransform: 'uppercase' }}>{mode.mode}</strong></div>
                  <div>Chunk Delay: <strong>{lastChunkDelayMs !== null ? `${lastChunkDelayMs} ms` : 'Measuring...'}</strong></div>
                  {lastNetStats.simulated && <div style={{ color: '#f59e0b', gridColumn: 'span 2' }}>⚠ simulated values</div>}
                </div>
              ) : (
                <p style={{ fontSize: '11px', opacity: 0.8, color: 'var(--vaak-muted-lilac)' }}>
                  Waiting for WebRTC statistics…
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

      {/* Footer Controls */}
      <footer className="conf-footer">
        <div className="controls-group">
          <TrackToggle source={Track.Source.Microphone} className="control-btn" />
          <TrackToggle source={Track.Source.Camera} className="control-btn" />

          {session.isHost && (
            <button
              onClick={handleEndMeetingForAll}
              className="control-btn btn-leave"
              style={{ backgroundColor: 'rgba(239, 68, 68, 0.3)' }}
              title="End meeting for all participants"
            >
              <ShieldAlert size={16} />
              <span>End for All</span>
            </button>
          )}

          <button onClick={handleLeaveCall} className="control-btn btn-leave">
            <PhoneOff size={16} />
            <span>Leave Meeting</span>
          </button>
        </div>
      </footer>

      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

function findStatsSources(room) {
  const engine = room?.engine;
  const pcm = engine?.pcManager;
  const candidates = [
    pcm?.publisher ?? engine?.publisher,
    pcm?.subscriber ?? engine?.subscriber,
  ];

  return candidates.map((t) => {
    if (!t) return null;
    const pc = t.pc ?? t._pc;
    if (pc && typeof pc.getStats === 'function') return pc;
    if (typeof t.getStats === 'function') return t;
    return null;
  });
}

function LiveKitController({ onRegisterStatsGetter, onMuteChange }) {
  const room = useRoomContext();

  useEffect(() => {
    if (!room) return;

    const tracker = createStatsTracker();
    let warned = false;

    const getStats = async () => {
      const sources = findStatsSources(room);
      if (!sources[0] && !sources[1]) {
        if (!warned) {
          warned = true;
          console.warn('[VAAK] No RTCPeerConnection found on room.engine.');
        }
        return null;
      }
      const reports = await Promise.all(
        sources.map((s) => (s ? s.getStats().catch(() => null) : Promise.resolve(null)))
      );
      return tracker(reports);
    };

    onRegisterStatsGetter(getStats);

    const checkMuteState = () => {
      const isMuted = !room.localParticipant.isMicrophoneEnabled;
      onMuteChange(isMuted);
    };

    room.on(RoomEvent.TrackMuted, checkMuteState);
    room.on(RoomEvent.TrackUnmuted, checkMuteState);
    room.on(RoomEvent.LocalTrackPublished, checkMuteState);
    room.on(RoomEvent.LocalTrackUnpublished, checkMuteState);

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
