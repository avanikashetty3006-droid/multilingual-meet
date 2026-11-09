import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
} from '@livekit/components-react';
import { Track } from 'livekit-client';

import { JoinScreen } from './JoinScreen';
import { VideoGrid } from './VideoGrid';
import { SubtitlePanel } from './SubtitlePanel';
import { useRoomSocket } from './useRoomSocket';
import { MicCaptureManager } from './micWorklet';
import { AudioQueue } from './audioQueue';

const CALL_SERVER_URL = import.meta.env.VITE_CALL_SERVER_URL || 'http://localhost:8000';

export default function App() {
  const [session, setSession] = useState(null); // { roomId, participantId, name, lang, token, livekitUrl }
  const [mainCaptions, setMainCaptions] = useState([]);
  const [overlapCaptions, setOverlapCaptions] = useState([]);
  const [showDebug, setShowDebug] = useState(false);

  const audioQueueRef = useRef(null);
  const micManagerRef = useRef(null);

  // Initialize audio queue
  useEffect(() => {
    audioQueueRef.current = new AudioQueue();
    return () => audioQueueRef.current?.clear();
  }, []);

  const handleTranslation = useCallback((msg) => {
    if (msg.lane === 'overlap') {
      setOverlapCaptions((prev) => [msg, ...prev].slice(0, 30));
    } else {
      setMainCaptions((prev) => [msg, ...prev].slice(0, 50));
    }

    // Play translated speech if audio_url provided and listener mode is audio
    if (msg.audio_url && msg.mode === 'audio') {
      audioQueueRef.current?.enqueue(msg.audio_url);
    }
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
  });

  // Start Mic Audio Streaming to Call Server on join
  useEffect(() => {
    if (!session) return;

    const wsProto = CALL_SERVER_URL.startsWith('https') ? 'wss' : 'ws';
    const host = CALL_SERVER_URL.replace(/^https?:\/\//, '');
    const audioWsUrl = `${wsProto}://${host}/ws/audio/${session.roomId}/${session.participantId}`;

    const micManager = new MicCaptureManager(audioWsUrl);
    micManagerRef.current = micManager;

    micManager.start().catch((err) => {
      console.warn('Microphone capture stream failed to start:', err);
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
  };

  const handleLangChange = (e) => {
    const newLang = e.target.value;
    setSession((prev) => ({ ...prev, lang: newLang }));
    setLanguage(newLang);
  };

  if (!session) {
    return <JoinScreen onJoin={handleJoin} />;
  }

  const isAudioMode = mode.mode === 'audio';

  return (
    <LiveKitRoom
      token={session.token}
      serverUrl={session.livekitUrl}
      connect={true}
      audio={true}
      video={true}
      className="conference-shell"
    >
      {/* Top Navigation Bar */}
      <header className="conf-header">
        <div className="header-left">
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
            </select>
          </label>
          <button
            onClick={() => setShowDebug(!showDebug)}
            className="btn-debug-toggle"
          >
            {showDebug ? 'Hide Stats' : 'Stats'}
          </button>
        </div>
      </header>

      {/* Main Conference Content: Video Grid + Subtitles */}
      <div className="conf-body">
        <main className="conf-stage">
          <VideoGrid activeSpeaker={activeSpeaker} />

          {/* Debug panel */}
          {showDebug && lastNetStats && (
            <div className="debug-card">
              <h4>Real-time Network Diagnostics</h4>
              <div className="debug-grid">
                <div>RTT: <strong>{lastNetStats.rtt_ms} ms</strong></div>
                <div>Packet Loss: <strong>{lastNetStats.packet_loss_pct}%</strong></div>
                <div>Bitrate: <strong>{lastNetStats.bitrate_kbps} kbps</strong></div>
                <div>Jitter: <strong>{lastNetStats.jitter_ms} ms</strong></div>
                <div>Current Mode: <strong>{mode.mode}</strong></div>
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
