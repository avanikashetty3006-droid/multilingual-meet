import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  Copy,
  Check,
  Globe,
  AlertTriangle,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

const SUPPORTED_LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi (हिंदी)' },
  { code: 'kn', label: 'Kannada (ಕನ್ನಡ)' },
  { code: 'ta', label: 'Tamil (தமிழ்)' },
  { code: 'te', label: 'Telugu (తెలుగు)' },
  { code: 'ml', label: 'Malayalam (മലയാളം)' },
  { code: 'mr', label: 'Marathi (मराठी)' },
];

/**
 * JoinScreen Component (Pre-Join Lobby)
 * Real-time camera and microphone preview, device selection, display name, listening language,
 * and clear browser permission guidance.
 */
export function JoinScreen({ onJoin, initialRoomId = 'room-alpha', user, onReplayIntro, onSignOut }) {
  const [roomId, setRoomId] = useState(initialRoomId);
  const [name, setName] = useState(user?.display_name || user?.name || '');
  const [lang, setLang] = useState(user?.default_lang || 'hi');
  const [micEnabled, setMicEnabled] = useState(user?.mic_default ?? true);
  const [camEnabled, setCamEnabled] = useState(user?.cam_default ?? true);

  const videoPreviewRef = useRef(null);
  const streamRef = useRef(null);
  const [permissionError, setPermissionError] = useState(null);
  const [videoDevices, setVideoDevices] = useState([]);
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedVideoDevice, setSelectedVideoDevice] = useState('');
  const [selectedAudioDevice, setSelectedAudioDevice] = useState('');
  const [isJoining, setIsJoining] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    let localStream = null;

    const startMedia = async () => {
      try {
        setPermissionError(null);
        const constraints = {
          video: selectedVideoDevice ? { deviceId: { exact: selectedVideoDevice } } : true,
          audio: selectedAudioDevice ? { deviceId: { exact: selectedAudioDevice } } : true,
        };

        localStream = await navigator.mediaDevices.getUserMedia(constraints);
        streamRef.current = localStream;

        if (videoPreviewRef.current) {
          videoPreviewRef.current.srcObject = localStream;
        }

        localStream.getVideoTracks().forEach((track) => {
          track.enabled = camEnabled;
        });
        localStream.getAudioTracks().forEach((track) => {
          track.enabled = micEnabled;
        });

        const devices = await navigator.mediaDevices.enumerateDevices();
        setVideoDevices(devices.filter((d) => d.kind === 'videoinput'));
        setAudioDevices(devices.filter((d) => d.kind === 'audioinput'));
      } catch (err) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setPermissionError(
            'Camera and microphone access was denied. To enable: click the lock/tune icon in your browser address bar, set Camera & Microphone to "Allow", then refresh.'
          );
        } else if (err.name === 'NotFoundError') {
          setPermissionError('No camera or microphone found on this device.');
        } else {
          setPermissionError(`Media device error: ${err.message || 'Check settings.'}`);
        }
      }
    };

    if (navigator.mediaDevices?.getUserMedia) {
      startMedia();
    }

    return () => {
      if (localStream) {
        localStream.getTracks().forEach((t) => t.stop());
      }
    };
  }, [selectedVideoDevice, selectedAudioDevice]);

  const toggleCam = () => {
    const next = !camEnabled;
    setCamEnabled(next);
    if (streamRef.current) {
      streamRef.current.getVideoTracks().forEach((t) => {
        t.enabled = next;
      });
    }
  };

  const toggleMic = () => {
    const next = !micEnabled;
    setMicEnabled(next);
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach((t) => {
        t.enabled = next;
      });
    }
  };

  const handleCopyLink = () => {
    const link = `${window.location.origin}/m/${roomId}`;
    navigator.clipboard.writeText(link);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      alert('Please enter your name');
      return;
    }
    if (!roomId.trim()) {
      alert('Please enter a room name');
      return;
    }

    setIsJoining(true);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    const participantId = `p-${Math.random().toString(36).substring(2, 8)}`;

    try {
      await onJoin({
        roomId: roomId.trim().toLowerCase(),
        participantId,
        name: name.trim(),
        lang,
        initialMic: micEnabled,
        initialCam: camEnabled,
      });
    } catch (err) {
      alert(err.message || 'Failed to join room');
      setIsJoining(false);
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: '1020px' }}>
      {/* Top account bar */}
      {user && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div className="user-avatar-placeholder" style={{ width: '32px', height: '32px', fontSize: '12px' }}>
              {(user.display_name || user.name || 'U').charAt(0).toUpperCase()}
            </div>
            <span style={{ fontSize: '0.9rem', color: 'var(--text-main)', fontWeight: 600 }}>{user.display_name || user.name}</span>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            {onReplayIntro && (
              <button type="button" onClick={onReplayIntro} className="btn-outline" style={{ fontSize: '0.78rem', padding: '4px 10px' }}>
                Replay Intro
              </button>
            )}
            {onSignOut && (
              <button type="button" onClick={onSignOut} style={{ background: 'none', border: 'none', color: '#ef4444', fontSize: '0.82rem', cursor: 'pointer', textDecoration: 'underline' }}>
                Sign out
              </button>
            )}
          </div>
        </div>
      )}

      <header className="page-header" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <Sparkles size={16} color="var(--vaak-muted-lilac)" />
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--vaak-muted-lilac)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Pre-Join Lobby
          </span>
        </div>
        <h1 className="page-title">Meeting: {roomId}</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px' }}>
          <button
            onClick={handleCopyLink}
            style={{ fontSize: '0.78rem', color: 'var(--vaak-muted-lilac)', display: 'inline-flex', alignItems: 'center', gap: '4px', background: 'none' }}
          >
            {copiedLink ? <Check size={14} color="var(--status-online)" /> : <Copy size={14} />}
            <span>{copiedLink ? 'Copied' : 'Copy invite link'}</span>
          </button>
        </div>
      </header>

      {permissionError && (
        <div
          style={{
            backgroundColor: 'rgba(245, 158, 11, 0.15)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            color: '#fbbf24',
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.85rem',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
          }}
        >
          <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>{permissionError}</div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '2rem' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div
            style={{
              position: 'relative',
              width: '100%',
              aspectRatio: '16/9',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--vaak-black-aubergine)',
              border: '1px solid var(--border-subtle)',
              overflow: 'hidden',
              boxShadow: 'var(--shadow-md)',
            }}
          >
            <video
              ref={videoPreviewRef}
              autoPlay
              playsInline
              muted
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                transform: 'scaleX(-1)',
                display: camEnabled ? 'block' : 'none',
              }}
            />

            {!camEnabled && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                <div className="user-avatar-placeholder" style={{ width: '70px', height: '70px', fontSize: '1.8rem', marginBottom: '10px' }}>
                  {(name || 'U').charAt(0).toUpperCase()}
                </div>
                <span style={{ fontSize: '0.85rem' }}>Camera is turned off</span>
              </div>
            )}

            <div style={{ position: 'absolute', bottom: '14px', left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: '12px', zIndex: 10 }}>
              <button
                type="button"
                onClick={toggleMic}
                className="btn-icon"
                style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: '50%',
                  backgroundColor: micEnabled ? 'rgba(33, 21, 38, 0.85)' : '#ef4444',
                  color: '#ffffff',
                }}
              >
                {micEnabled ? <Mic size={20} /> : <MicOff size={20} />}
              </button>

              <button
                type="button"
                onClick={toggleCam}
                className="btn-icon"
                style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: '50%',
                  backgroundColor: camEnabled ? 'rgba(33, 21, 38, 0.85)' : '#ef4444',
                  color: '#ffffff',
                }}
              >
                {camEnabled ? <Video size={20} /> : <VideoOff size={20} />}
              </button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div className="input-group" style={{ marginBottom: 0 }}>
              <label className="input-label">Camera</label>
              <select
                value={selectedVideoDevice}
                onChange={(e) => setSelectedVideoDevice(e.target.value)}
                className="select-custom"
                style={{ fontSize: '0.82rem', padding: '0.6rem 0.8rem' }}
              >
                {videoDevices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label || `Camera ${d.deviceId.slice(0, 5)}`}
                  </option>
                ))}
              </select>
            </div>

            <div className="input-group" style={{ marginBottom: 0 }}>
              <label className="input-label">Microphone</label>
              <select
                value={selectedAudioDevice}
                onChange={(e) => setSelectedAudioDevice(e.target.value)}
                className="select-custom"
                style={{ fontSize: '0.82rem', padding: '0.6rem 0.8rem' }}
              >
                {audioDevices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label || `Microphone ${d.deviceId.slice(0, 5)}`}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="vaak-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <form onSubmit={handleSubmit}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>
              Participant Setup
            </h3>

            <div className="input-group">
              <label className="input-label">Your Display Name</label>
              <input
                type="text"
                className="input-text"
                placeholder="e.g. Asha Rao"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div className="input-group">
              <label className="input-label">Meeting Room ID</label>
              <input
                type="text"
                className="input-text"
                value={roomId}
                onChange={(e) => setRoomId(e.target.value)}
                required
              />
            </div>

            <div className="input-group">
              <label className="input-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Globe size={15} color="var(--vaak-muted-lilac)" />
                <span>Listening Language (Auto-Translated For You)</span>
              </label>
              <select
                value={lang}
                onChange={(e) => setLang(e.target.value)}
                className="select-custom"
              >
                {SUPPORTED_LANGS.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginTop: '2rem' }}>
              <button
                type="submit"
                disabled={isJoining || !name.trim() || !roomId.trim()}
                className="btn-primary"
                style={{ width: '100%', padding: '0.95rem 1.6rem', fontSize: '1.02rem' }}
              >
                <span>{isJoining ? 'Connecting to Room...' : 'Join Meeting Now'}</span>
                <ArrowRight size={18} />
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
