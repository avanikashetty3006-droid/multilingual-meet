import React, { useState } from 'react';

const SUPPORTED_LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi (हिंदी)' },
  { code: 'kn', label: 'Kannada (ಕನ್ನಡ)' },
  { code: 'ta', label: 'Tamil (தமிழ்)' },
  { code: 'te', label: 'Telugu (తెలుగు)' },
  { code: 'ml', label: 'Malayalam (മലയാളം)' },
  { code: 'mr', label: 'Marathi (मराठी)' },
];

export function JoinScreen({ onJoin, initialRoomId = 'room-alpha', user, onReplayIntro, onSignOut }) {
  const [roomId, setRoomId] = useState(initialRoomId);
  const [name, setName] = useState(user?.name || '');
  const [lang, setLang] = useState('hi');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Please enter your name');
      return;
    }
    if (!roomId.trim()) {
      setError('Please enter a room name');
      return;
    }

    setIsLoading(true);
    setError('');

    const participantId = `p-${Math.random().toString(36).substring(2, 8)}`;

    try {
      await onJoin({
        roomId: roomId.trim().toLowerCase(),
        participantId,
        name: name.trim(),
        lang,
      });
    } catch (err) {
      setError(err.message || 'Failed to join room');
      setIsLoading(false);
    }
  };

  return (
    <div className="join-shell">
      <div className="join-card">
        {/* Top account bar */}
        {user && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: '#D3A376', color: '#3E2522', fontWeight: 'bold', fontSize: '11px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {user.avatar || 'U'}
              </div>
              <span style={{ fontSize: '12px', color: 'var(--text-main)', fontWeight: 600 }}>{user.name}</span>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              {onReplayIntro && (
                <button type="button" onClick={onReplayIntro} style={{ background: 'none', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-muted)', fontSize: '11px', padding: '3px 8px', cursor: 'pointer' }}>
                  Replay Intro
                </button>
              )}
              {onSignOut && (
                <button type="button" onClick={onSignOut} style={{ background: 'none', border: 'none', color: '#ef4444', fontSize: '11px', cursor: 'pointer', textDecoration: 'underline' }}>
                  Sign out
                </button>
              )}
            </div>
          </div>
        )}

        <div className="join-header">
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '0.75rem' }}>
            <img src="/vaak_logo.png" alt="VAAK Logo" style={{ height: '56px', width: 'auto', objectFit: 'contain' }} onError={(e) => { e.currentTarget.src = './src/assets/vaak_logo.png'; }} />
          </div>
          <p className="subtitle">Real-time video conferencing with automatic AI translation & speech synthesis</p>
        </div>

        <form onSubmit={handleSubmit} className="join-form">
          {error && <div className="alert-box error">{error}</div>}

          <div className="field-group">
            <label htmlFor="name">Your Name</label>
            <input
              id="name"
              type="text"
              placeholder="e.g. Asha Rao"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="field-group">
            <label htmlFor="roomId">Room Name</label>
            <input
              id="roomId"
              type="text"
              placeholder="e.g. project-sync"
              value={roomId}
              onChange={(e) => setRoomId(e.target.value)}
              required
            />
          </div>

          <div className="field-group">
            <label htmlFor="lang">Your Listening Language</label>
            <select
              id="lang"
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="select-input"
            >
              {SUPPORTED_LANGS.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
            <small className="help-text">Speech from others will be translated to this language for you.</small>
          </div>

          <button type="submit" className="btn-join" disabled={isLoading}>
            {isLoading ? 'Joining Meeting...' : 'Join Call'}
          </button>
        </form>
      </div>
    </div>
  );
}
