import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User,
  Globe,
  Mic,
  Video,
  FileText,
  Moon,
  Sparkles,
  LogOut,
  AlertTriangle,
  Check,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const SUPPORTED_LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi (हिंदी)' },
  { code: 'kn', label: 'Kannada (ಕನ್ನಡ)' },
  { code: 'ta', label: 'Tamil (தமிழ்)' },
  { code: 'te', label: 'Telugu (తెలుగు)' },
  { code: 'ml', label: 'Malayalam (മലയാളം)' },
  { code: 'mr', label: 'Marathi (मराठी)' },
];

export function SettingsView() {
  const { user, updateProfile, signOut, deleteAccount, replayIntro } = useAuth();
  const navigate = useNavigate();

  // Settings form state
  const [displayName, setDisplayName] = useState(user?.display_name || user?.name || '');
  const [defaultLang, setDefaultLang] = useState(user?.default_lang || 'hi');
  const [micDefault, setMicDefault] = useState(user?.mic_default ?? true);
  const [camDefault, setCamDefault] = useState(user?.cam_default ?? true);
  const [subtitlesOnly, setSubtitlesOnly] = useState(user?.subtitles_only ?? false);
  const [theme, setTheme] = useState(user?.theme || 'dark');

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveSuccess(false);

    try {
      await updateProfile({
        display_name: displayName.trim(),
        default_lang: defaultLang,
        mic_default: micDefault,
        cam_default: camDefault,
        subtitles_only: subtitlesOnly,
        theme,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      alert('Failed to save settings: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReplayIntro = () => {
    replayIntro();
  };

  const handleSignOut = async () => {
    await signOut();
    navigate('/signin');
  };

  const handleDeleteAccount = async () => {
    setIsDeleting(true);
    try {
      await deleteAccount();
      navigate('/signin');
    } catch (err) {
      alert('Failed to delete account: ' + err.message);
      setIsDeleting(false);
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: '840px' }}>
      <header className="page-header">
        <h1 className="page-title">Profile & Settings</h1>
        <p className="page-subtitle">
          Manage your identity, language preferences, conferencing defaults, and theme.
        </p>
      </header>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
        {/* Profile Card */}
        <section className="vaak-card">
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <User size={18} color="var(--vaak-muted-lilac)" />
            <span>Google Account Identity</span>
          </h2>

          <div style={{ display: 'flex', alignItems: 'center', gap: '18px', marginBottom: '1.5rem' }}>
            {user?.picture ? (
              <img
                src={user.picture}
                alt={user.name || 'User'}
                style={{ width: '64px', height: '64px', borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--border-glow)' }}
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="user-avatar-placeholder" style={{ width: '64px', height: '64px', fontSize: '1.5rem' }}>
                {(user?.name || 'U').charAt(0).toUpperCase()}
              </div>
            )}
            <div>
              <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--text-main)' }}>
                {user?.name}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {user?.email}
              </div>
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Conference Display Name</label>
            <input
              type="text"
              className="input-text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              This is the name visible to other participants in the video grid and captions.
            </span>
          </div>
        </section>

        {/* Translation & Media Defaults Card */}
        <section className="vaak-card">
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Globe size={18} color="var(--vaak-muted-lilac)" />
            <span>Multilingual & Media Defaults</span>
          </h2>

          <div className="input-group">
            <label className="input-label">Default Listening Language</label>
            <select
              value={defaultLang}
              onChange={(e) => setDefaultLang(e.target.value)}
              className="select-custom"
            >
              {SUPPORTED_LANGS.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Calls will automatically start with speech translated into this target language.
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '1rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={micDefault}
                onChange={(e) => setMicDefault(e.target.checked)}
                style={{ width: '18px', height: '18px', accentColor: 'var(--vaak-soft-plum)' }}
              />
              <div>
                <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-main)' }}>Join with Microphone On</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Automatically enable audio input upon entering a call.</div>
              </div>
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={camDefault}
                onChange={(e) => setCamDefault(e.target.checked)}
                style={{ width: '18px', height: '18px', accentColor: 'var(--vaak-soft-plum)' }}
              />
              <div>
                <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-main)' }}>Join with Camera On</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Automatically enable video stream upon entering a call.</div>
              </div>
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={subtitlesOnly}
                onChange={(e) => setSubtitlesOnly(e.target.checked)}
                style={{ width: '18px', height: '18px', accentColor: 'var(--vaak-soft-plum)' }}
              />
              <div>
                <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-main)' }}>Subtitles Only (Save Bandwidth)</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Always prefer text translation over synthetic voice playback.</div>
              </div>
            </label>
          </div>
        </section>

        {/* Theme & Experience Card */}
        <section className="vaak-card">
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Moon size={18} color="var(--vaak-muted-lilac)" />
            <span>Theme & Cinematic Experience</span>
          </h2>

          <div className="input-group">
            <label className="input-label">App Appearance Theme</label>
            <select
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              className="select-custom"
            >
              <option value="dark">Dark Theme (Aubergine & Onyx)</option>
              <option value="light">Light Theme (Plum & Crisp Lilac)</option>
              <option value="system">Follow System Preference</option>
            </select>
          </div>

          <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-subtle)' }}>
            <button
              type="button"
              onClick={handleReplayIntro}
              className="btn-secondary"
            >
              <Sparkles size={16} />
              <span>Replay Intro Animation</span>
            </button>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginTop: '6px' }}>
              Watch the world-to-logo assembly sequence again.
            </span>
          </div>
        </section>

        {/* Action Bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              type="submit"
              disabled={isSaving}
              className="btn-primary"
            >
              {saveSuccess ? <Check size={18} /> : null}
              <span>{isSaving ? 'Saving...' : saveSuccess ? 'Saved!' : 'Save Preferences'}</span>
            </button>
            {saveSuccess && (
              <span style={{ color: 'var(--status-online)', fontSize: '0.85rem' }}>
                Preferences updated successfully.
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={handleSignOut}
            className="btn-outline"
          >
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>

        {/* Danger Zone */}
        <section
          className="vaak-card"
          style={{
            borderColor: 'rgba(239, 68, 68, 0.3)',
            backgroundColor: 'rgba(239, 68, 68, 0.04)',
            marginTop: '1.5rem',
          }}
        >
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fca5a5', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={18} />
            <span>Danger Zone</span>
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem', lineHeight: 1.5 }}>
            Permanently delete your VAAK account, meeting history, and contact connections. This action is irreversible.
          </p>
          <button
            type="button"
            onClick={() => setShowDeleteModal(true)}
            className="btn-danger"
          >
            Delete Account and All Data
          </button>
        </section>
      </form>

      {/* Confirmation Modal for Account Deletion */}
      {showDeleteModal && (
        <div className="modal-backdrop" onClick={() => setShowDeleteModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#fca5a5', marginBottom: '0.75rem' }}>
              Confirm Account Deletion
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem', lineHeight: 1.5 }}>
              Are you sure you want to delete your account? All your meeting history, friend lists, and preferences will be permanently wiped.
            </p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                className="btn-outline"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteAccount}
                disabled={isDeleting}
                className="btn-danger"
              >
                {isDeleting ? 'Deleting...' : 'Yes, Delete My Account'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
