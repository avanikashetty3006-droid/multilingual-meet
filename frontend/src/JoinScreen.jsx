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

export function JoinScreen({ onJoin, initialRoomId = 'room-alpha' }) {
  const [roomId, setRoomId] = useState(initialRoomId);
  const [name, setName] = useState('');
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
        <div className="join-header">
          <h1 className="brand-title">Multilingual Meet</h1>
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
