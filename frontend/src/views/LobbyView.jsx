import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
import { useAuth } from '../context/AuthContext';
import { api, ApiError } from '../api/client';

const ConferenceView = React.lazy(() =>
  import('./ConferenceView').then((m) => ({ default: m.ConferenceView }))
);

const SUPPORTED_LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi (हिंदी)' },
  { code: 'kn', label: 'Kannada (ಕನ್ನಡ)' },
  { code: 'ta', label: 'Tamil (தமிழ்)' },
  { code: 'te', label: 'Telugu (తెలుగు)' },
  { code: 'ml', label: 'Malayalam (മലയാളം)' },
  { code: 'mr', label: 'Marathi (मराठी)' },
];

export function LobbyView() {
  const { id: meetingId } = useParams();
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  // Meeting verification state
  const [meetingInfo, setMeetingInfo] = useState(null);
  const [meetingError, setMeetingError] = useState(null);
  const [isVerifying, setIsVerifying] = useState(true);

  // User lobby preferences
  const [displayName, setDisplayName] = useState('');
  const [listeningLang, setListeningLang] = useState('hi');
  const [micEnabled, setMicEnabled] = useState(true);
  const [camEnabled, setCamEnabled] = useState(true);

  // Device streams and permissions
  const videoPreviewRef = useRef(null);
  const streamRef = useRef(null);
  const [permissionError, setPermissionError] = useState(null);
  const [videoDevices, setVideoDevices] = useState([]);
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedVideoDevice, setSelectedVideoDevice] = useState('');
  const [selectedAudioDevice, setSelectedAudioDevice] = useState('');

  // Active call session state
  const [activeSession, setActiveSession] = useState(null);
  const [isJoining, setIsJoining] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  // 1. Deep Link Auth Check: if not authenticated and auth check finished, redirect to signin
  useEffect(() => {
    if (!authLoading && !user) {
      navigate(`/signin?redirect=/m/${meetingId}`, { replace: true });
    }
  }, [authLoading, user, meetingId, navigate]);

  // 2. Set default user settings
  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name || user.name || '');
      setListeningLang(user.default_lang || 'hi');
      if (user.mic_default !== undefined) setMicEnabled(user.mic_default);
      if (user.cam_default !== undefined) setCamEnabled(user.cam_default);
    }
  }, [user]);

  // 3. Verify meeting on the server
  useEffect(() => {
    let mounted = true;
    const verify = async () => {
      try {
        const info = await api.meetings.get(meetingId);
        if (mounted) {
          if (info.active === false) {
            setMeetingError('This meeting has ended.');
          } else {
            setMeetingInfo(info);
          }
        }
      } catch (err) {
        if (mounted) {
          if (err instanceof ApiError && err.status === 404) {
            setMeetingError('Meeting not found. Please check the URL.');
          } else {
            setMeetingError(err.message || 'Unable to load meeting information.');
          }
        }
      } finally {
        if (mounted) setIsVerifying(false);
      }
    };

    if (meetingId && user) {
      verify();
    }
    return () => {
      mounted = false;
    };
  }, [meetingId, user]);

  // 4. Initialize Local Media Preview (Camera & Mic)
  useEffect(() => {
    if (!user || activeSession) return;

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

        // Apply initial toggle states
        localStream.getVideoTracks().forEach((track) => {
          track.enabled = camEnabled;
        });
        localStream.getAudioTracks().forEach((track) => {
          track.enabled = micEnabled;
        });

        // Enumerate devices
        const devices = await navigator.mediaDevices.enumerateDevices();
        setVideoDevices(devices.filter((d) => d.kind === 'videoinput'));
        setAudioDevices(devices.filter((d) => d.kind === 'audioinput'));
      } catch (err) {
        console.warn('Media access failed in lobby:', err);
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setPermissionError(
            'Camera and microphone access was denied. To enable: click the tune/lock icon in your browser address bar and set Camera and Microphone to "Allow", then refresh.'
          );
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          setPermissionError('No camera or microphone found on this device.');
        } else {
          setPermissionError(`Media device error: ${err.message || 'Check your settings.'}`);
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
  }, [user, activeSession, selectedVideoDevice, selectedAudioDevice]);

  // Handle toggles
  const toggleCam = () => {
    const nextState = !camEnabled;
    setCamEnabled(nextState);
    if (streamRef.current) {
      streamRef.current.getVideoTracks().forEach((t) => {
        t.enabled = nextState;
      });
    }
  };

  const toggleMic = () => {
    const nextState = !micEnabled;
    setMicEnabled(nextState);
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach((t) => {
        t.enabled = nextState;
      });
    }
  };

  const handleCopyLink = () => {
    const link = `${window.location.origin}/m/${meetingId}`;
    navigator.clipboard.writeText(link);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  // Join meeting handler
  const handleJoinMeeting = async () => {
    if (!displayName.trim()) {
      alert('Please enter your display name.');
      return;
    }

    setIsJoining(true);
    try {
      // Clean up lobby media stream before handing over to LiveKit
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }

      const res = await api.meetings.join(meetingId, {
        display_name: displayName.trim(),
        lang: listeningLang,
      });

      setActiveSession({
        roomId: meetingId,
        participantId: `p-${Math.random().toString(36).substring(2, 8)}`,
        name: displayName.trim(),
        lang: listeningLang,
        token: res.livekit_token,
        livekitUrl: res.livekit_url || import.meta.env.VITE_LIVEKIT_URL,
        isHost: meetingInfo?.host_id === user?.id,
        initialMic: micEnabled,
        initialCam: camEnabled,
      });
    } catch (err) {
      alert(err.message || 'Failed to join meeting.');
    } finally {
      setIsJoining(false);
    }
  };

  // If active call session is running, render ConferenceView with Suspense
  if (activeSession) {
    return (
      <React.Suspense
        fallback={
          <div style={{ display: 'flex', height: '100vh', width: '100vw', alignItems: 'center', justifyContent: 'center', backgroundColor: '#090809', color: '#E8E2E8' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1.8rem', marginBottom: '12px' }}>📡</div>
              <div style={{ fontWeight: 600 }}>Connecting to LiveKit Room...</div>
            </div>
          </div>
        }
      >
        <ConferenceView
          session={activeSession}
          onLeave={() => {
            setActiveSession(null);
            navigate('/', { replace: true });
          }}
        />
      </React.Suspense>
    );
  }

  // Loading state
  if (authLoading || isVerifying) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--bg-app)' }}>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>Verifying meeting credentials...</div>
      </div>
    );
  }

  // Error state
  if (meetingError) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--bg-app)', padding: '1.5rem' }}>
        <div className="vaak-card" style={{ maxWidth: '440px', textAlign: 'center', padding: '2.5rem' }}>
          <div style={{ fontSize: '2.2rem', marginBottom: '0.8rem' }}>🚫</div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '0.5rem' }}>Meeting Unavailable</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>{meetingError}</p>
          <button onClick={() => navigate('/')} className="btn-primary" style={{ width: '100%' }}>
            Return to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" style={{ maxWidth: '1020px' }}>
      <header className="page-header" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <Sparkles size={16} color="var(--vaak-muted-lilac)" />
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--vaak-muted-lilac)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Pre-Join Lobby
          </span>
        </div>
        <h1 className="page-title">{meetingInfo?.title || `Meeting ${meetingId}`}</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px' }}>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Room ID: <code>{meetingId}</code></span>
          <button
            onClick={handleCopyLink}
            style={{ fontSize: '0.78rem', color: 'var(--vaak-muted-lilac)', display: 'inline-flex', alignItems: 'center', gap: '4px', background: 'none' }}
          >
            {copiedLink ? <Check size={14} color="var(--status-online)" /> : <Copy size={14} />}
            <span>{copiedLink ? 'Copied' : 'Copy invite link'}</span>
          </button>
        </div>
      </header>

      {/* Permission Warning Banner */}
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
            lineHeight: 1.45,
          }}
        >
          <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>{permissionError}</div>
        </div>
      )}

      {/* Lobby Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '2rem' }}>
        {/* Left Column: Video Preview and Controls */}
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
                transform: 'scaleX(-1)', // mirror selfie video
                display: camEnabled ? 'block' : 'none',
              }}
            />

            {!camEnabled && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  color: 'var(--text-muted)',
                }}
              >
                <div
                  className="user-avatar-placeholder"
                  style={{ width: '70px', height: '70px', fontSize: '1.8rem', marginBottom: '10px' }}
                >
                  {(displayName || 'U').charAt(0).toUpperCase()}
                </div>
                <span style={{ fontSize: '0.85rem' }}>Camera is turned off</span>
              </div>
            )}

            {/* Media Toggles floating on video */}
            <div
              style={{
                position: 'absolute',
                bottom: '14px',
                left: '50%',
                transform: 'translateX(-50%)',
                display: 'flex',
                gap: '12px',
                zIndex: 10,
              }}
            >
              <button
                onClick={toggleMic}
                className="btn-icon"
                style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: '50%',
                  backgroundColor: micEnabled ? 'rgba(33, 21, 38, 0.85)' : '#ef4444',
                  color: '#ffffff',
                  border: '1px solid rgba(162, 143, 165, 0.3)',
                }}
                title={micEnabled ? 'Mute microphone' : 'Unmute microphone'}
              >
                {micEnabled ? <Mic size={20} /> : <MicOff size={20} />}
              </button>

              <button
                onClick={toggleCam}
                className="btn-icon"
                style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: '50%',
                  backgroundColor: camEnabled ? 'rgba(33, 21, 38, 0.85)' : '#ef4444',
                  color: '#ffffff',
                  border: '1px solid rgba(162, 143, 165, 0.3)',
                }}
                title={camEnabled ? 'Turn camera off' : 'Turn camera on'}
              >
                {camEnabled ? <Video size={20} /> : <VideoOff size={20} />}
              </button>
            </div>
          </div>

          {/* Device Selection dropdowns */}
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

        {/* Right Column: Participant Preferences & Join Action */}
        <div className="vaak-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>
              Participant Setup
            </h3>

            <div className="input-group">
              <label className="input-label">Your Display Name</label>
              <input
                type="text"
                className="input-text"
                placeholder="e.g. Asha Rao"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
              />
            </div>

            <div className="input-group">
              <label className="input-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Globe size={15} color="var(--vaak-muted-lilac)" />
                <span>Listening Language (Auto-Translated For You)</span>
              </label>
              <select
                value={listeningLang}
                onChange={(e) => setListeningLang(e.target.value)}
                className="select-custom"
              >
                {SUPPORTED_LANGS.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                You will hear/read all other participants automatically translated into this language.
              </span>
            </div>
          </div>

          <div style={{ marginTop: '2rem' }}>
            <button
              onClick={handleJoinMeeting}
              disabled={isJoining || !displayName.trim()}
              className="btn-primary"
              style={{ width: '100%', padding: '0.95rem 1.6rem', fontSize: '1.02rem' }}
            >
              <span>{isJoining ? 'Connecting to Room...' : 'Join Meeting Now'}</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
