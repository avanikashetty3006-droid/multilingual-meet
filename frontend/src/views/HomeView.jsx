import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Video,
  PlusCircle,
  LogIn,
  Copy,
  Check,
  Calendar,
  Users,
  Clock,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api, ApiError } from '../api/client';
import { parseMeetingId, isValidMeetingId } from '../utils/meetingId';

export function HomeView() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // New Meeting State
  const [isCreating, setIsCreating] = useState(false);
  const [createdMeeting, setCreatedMeeting] = useState(null);
  const [copiedLink, setCopiedLink] = useState(false);

  // Join State
  const [joinInput, setJoinInput] = useState('');
  const [joinError, setJoinError] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);

  // Recent meetings & online friends
  const [recentMeetings, setRecentMeetings] = useState([]);
  const [onlineFriends, setOnlineFriends] = useState([]);
  const [isLoadingData, setIsLoadingData] = useState(true);

  useEffect(() => {
    let mounted = true;
    const loadOverview = async () => {
      try {
        const [histRes, friendsRes] = await Promise.allSettled([
          api.meetings.getHistory(),
          api.friends.list(),
        ]);

        if (mounted) {
          if (histRes.status === 'fulfilled' && histRes.value?.items) {
            setRecentMeetings(histRes.value.items.slice(0, 3));
          }
          if (friendsRes.status === 'fulfilled' && Array.isArray(friendsRes.value)) {
            setOnlineFriends(friendsRes.value.filter((f) => f.presence === 'online').slice(0, 4));
          }
        }
      } finally {
        if (mounted) setIsLoadingData(false);
      }
    };

    loadOverview();
    return () => {
      mounted = false;
    };
  }, []);

  // Handle New Meeting Creation
  const handleCreateMeeting = async () => {
    setIsCreating(true);
    try {
      const meeting = await api.meetings.create();
      setCreatedMeeting(meeting);
    } catch (err) {
      alert(err.message || 'Failed to create meeting.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopyLink = () => {
    if (!createdMeeting) return;
    const url = createdMeeting.join_url || `${window.location.origin}/m/${createdMeeting.id}`;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleGoToLobby = () => {
    if (createdMeeting) {
      navigate(`/m/${createdMeeting.id}`);
    }
  };

  // Handle Join by ID or URL
  const handleJoinSubmit = async (e) => {
    e.preventDefault();
    setJoinError('');

    const parsedId = parseMeetingId(joinInput);
    if (!parsedId || !isValidMeetingId(parsedId)) {
      setJoinError('Please enter a valid 10-character meeting ID or URL.');
      return;
    }

    setIsVerifying(true);
    try {
      const info = await api.meetings.get(parsedId);
      if (!info) {
        setJoinError('Meeting not found. Please verify the ID.');
        return;
      }
      if (info.active === false) {
        setJoinError('This meeting has already ended.');
        return;
      }
      navigate(`/m/${parsedId}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setJoinError('Meeting not found. Check the ID and try again.');
        } else {
          setJoinError(err.message || 'Unable to join meeting.');
        }
      } else {
        setJoinError('Network error. Check connection.');
      }
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="page-container">
      {/* Welcome Banner */}
      <header className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <Sparkles size={18} color="var(--vaak-muted-lilac)" />
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--vaak-muted-lilac)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Multilingual Video Hub
          </span>
        </div>
        <h1 className="page-title">
          Welcome back, {user?.display_name || user?.name || 'Friend'}
        </h1>
        <p className="page-subtitle">
          Real-time AI voice translation and subtitles in your listening language.
        </p>
      </header>

      {/* Two Big Actions Grid */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginBottom: '2.5rem' }}>
        {/* Action 1: New Meeting */}
        <div className="vaak-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, var(--vaak-smoked-plum), var(--vaak-muted-aubergine))',
                border: '1px solid var(--border-glow)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--vaak-warm-white)',
                marginBottom: '1.25rem',
              }}
            >
              <PlusCircle size={26} />
            </div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-main)' }}>
              New Meeting
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.5, marginBottom: '1.5rem' }}>
              Create an unguessable meeting room, get a shareable link, and invite participants with live speech translation.
            </p>
          </div>

          <button
            onClick={handleCreateMeeting}
            disabled={isCreating}
            className="btn-primary"
            style={{ width: '100%' }}
          >
            <Video size={18} />
            <span>{isCreating ? 'Generating Room...' : 'Start New Meeting'}</span>
          </button>
        </div>

        {/* Action 2: Join with ID or Link */}
        <div className="vaak-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--vaak-muted-lilac)',
                marginBottom: '1.25rem',
              }}
            >
              <LogIn size={26} />
            </div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-main)' }}>
              Join Meeting
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.5, marginBottom: '1rem' }}>
              Enter a meeting ID (e.g., <code>abc-defg-hij</code>) or paste the complete invite link.
            </p>
          </div>

          <form onSubmit={handleJoinSubmit}>
            <div className="input-group" style={{ marginBottom: '1rem' }}>
              <input
                type="text"
                className="input-text"
                placeholder="abc-defg-hij or https://..."
                value={joinInput}
                onChange={(e) => {
                  setJoinInput(e.target.value);
                  if (joinError) setJoinError('');
                }}
                aria-label="Meeting ID or link"
              />
              {joinError && (
                <div style={{ color: '#fca5a5', fontSize: '0.8rem', marginTop: '4px', textAlign: 'left' }}>
                  ⚠️ {joinError}
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={isVerifying || !joinInput.trim()}
              className="btn-secondary"
              style={{ width: '100%' }}
            >
              <span>{isVerifying ? 'Checking...' : 'Enter Lobby'}</span>
              <ArrowRight size={16} />
            </button>
          </form>
        </div>
      </section>

      {/* Quick Overview Split: Recent Meetings & Online Friends */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {/* Recent Meetings Strip */}
        <div className="vaak-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Calendar size={18} color="var(--vaak-muted-lilac)" />
              <span>Recent Meetings</span>
            </h3>
            <button
              onClick={() => navigate('/meetings')}
              style={{ fontSize: '0.82rem', color: 'var(--vaak-muted-lilac)', fontWeight: 600 }}
            >
              View all &rarr;
            </button>
          </div>

          {isLoadingData ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem', padding: '1rem 0' }}>
              Loading recent activity...
            </div>
          ) : recentMeetings.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem', padding: '1.5rem 0', textAlign: 'center' }}>
              No meetings attended yet. Start your first multilingual conference above!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {recentMeetings.map((m) => (
                <div
                  key={m.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {m.title || `Meeting ${m.id}`}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                      <span>{new Date(m.started_at).toLocaleDateString()}</span>
                      <span>&bull;</span>
                      <span>{m.role === 'host' ? 'Host' : 'Guest'}</span>
                      {m.active && (
                        <>
                          <span>&bull;</span>
                          <span style={{ color: 'var(--status-online)', fontWeight: 700 }}>Active Now</span>
                        </>
                      )}
                    </div>
                  </div>

                  {m.active ? (
                    <button
                      onClick={() => navigate(`/m/${m.id}`)}
                      className="btn-outline"
                      style={{ fontSize: '0.78rem', padding: '4px 10px' }}
                    >
                      Rejoin
                    </button>
                  ) : (
                    <button
                      onClick={() => navigate(`/m/${m.id}`)}
                      className="btn-outline"
                      style={{ fontSize: '0.78rem', padding: '4px 10px' }}
                    >
                      Enter
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Online Friends Strip */}
        <div className="vaak-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Users size={18} color="var(--vaak-muted-lilac)" />
              <span>Friends Online</span>
            </h3>
            <button
              onClick={() => navigate('/friends')}
              style={{ fontSize: '0.82rem', color: 'var(--vaak-muted-lilac)', fontWeight: 600 }}
            >
              Manage &rarr;
            </button>
          </div>

          {isLoadingData ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem', padding: '1rem 0' }}>
              Checking presence...
            </div>
          ) : onlineFriends.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem', padding: '1.5rem 0', textAlign: 'center' }}>
              None of your friends are online right now. Invite them via the Friends tab!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {onlineFriends.map((f) => (
                <div
                  key={f.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ position: 'relative' }}>
                      {f.picture ? (
                        <img
                          src={f.picture}
                          alt={f.display_name}
                          style={{ width: '32px', height: '32px', borderRadius: '50%', objectFit: 'cover' }}
                        />
                      ) : (
                        <div className="user-avatar-placeholder" style={{ width: '32px', height: '32px', fontSize: '0.75rem' }}>
                          {f.display_name.charAt(0)}
                        </div>
                      )}
                      <span
                        className="presence-dot online"
                        style={{ position: 'absolute', bottom: '0', right: '0', border: '1.5px solid var(--bg-card)' }}
                      />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.86rem', fontWeight: 600, color: 'var(--text-main)' }}>
                        {f.display_name}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {f.email}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(`${window.location.origin}`);
                      alert(`Meeting link copied to invite ${f.display_name}`);
                    }}
                    className="btn-outline"
                    style={{ fontSize: '0.75rem', padding: '3px 8px' }}
                  >
                    Invite
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Modal: New Meeting Share Dialog */}
      {createdMeeting && (
        <div className="modal-backdrop" onClick={() => setCreatedMeeting(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1.25rem' }}>
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, var(--vaak-smoked-plum), var(--vaak-muted-aubergine))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Video size={24} color="var(--vaak-warm-white)" />
              </div>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Your Meeting is Ready</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  Share the link with participants or join the lobby now.
                </p>
              </div>
            </div>

            <div className="input-group" style={{ marginBottom: '1.5rem' }}>
              <label className="input-label">Shareable Meeting Link</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  readOnly
                  value={createdMeeting.join_url || `${window.location.origin}/m/${createdMeeting.id}`}
                  className="input-text"
                  style={{ flex: 1, fontSize: '0.88rem' }}
                />
                <button
                  onClick={handleCopyLink}
                  className="btn-secondary"
                  title="Copy link"
                  style={{ padding: '0 14px' }}
                >
                  {copiedLink ? <Check size={18} color="var(--status-online)" /> : <Copy size={18} />}
                </button>
              </div>
              {copiedLink && (
                <span style={{ fontSize: '0.75rem', color: 'var(--status-online)', marginTop: '2px' }}>
                  ✓ Copied to clipboard!
                </span>
              )}
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setCreatedMeeting(null)}
                className="btn-outline"
              >
                Done
              </button>
              <button
                onClick={handleGoToLobby}
                className="btn-primary"
              >
                <span>Enter Lobby</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
