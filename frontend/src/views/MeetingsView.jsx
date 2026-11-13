import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Calendar,
  Clock,
  Users,
  Trash2,
  Video,
  ArrowRight,
  RotateCcw,
} from 'lucide-react';
import { api } from '../api/client';

export function MeetingsView() {
  const navigate = useNavigate();
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const fetchMeetings = async (cursor = null) => {
    try {
      const res = await api.meetings.getHistory(cursor);
      if (res?.items) {
        if (cursor) {
          setMeetings((prev) => [...prev, ...res.items]);
        } else {
          setMeetings(res.items);
        }
        setNextCursor(res.next_cursor || null);
      }
    } catch (err) {
      console.warn('Failed to load meetings history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMeetings();
  }, []);

  const handleDeleteItem = async (id, e) => {
    e.stopPropagation();
    if (!confirm('Remove this meeting from your history?')) return;

    setDeletingId(id);
    try {
      await api.meetings.deleteHistory(id);
      setMeetings((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      alert('Failed to remove meeting.');
    } finally {
      setDeletingId(null);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'Active';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins >= 60) {
      const hrs = Math.floor(mins / 60);
      const remMins = mins % 60;
      return `${hrs}h ${remMins}m`;
    }
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-title">Meeting History</h1>
        <p className="page-subtitle">
          Review past conferences, view participant counts, and rejoin active rooms.
        </p>
      </header>

      {loading ? (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.95rem', padding: '2rem 0' }}>
          Loading your meeting history...
        </div>
      ) : meetings.length === 0 ? (
        <div className="vaak-card" style={{ textAlign: 'center', padding: '3.5rem 1.5rem' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>📅</div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>No Meetings Found</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginBottom: '1.5rem' }}>
            Meetings you host or join will automatically appear here.
          </p>
          <button onClick={() => navigate('/')} className="btn-primary">
            <Video size={16} />
            <span>Create or Join a Meeting</span>
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {meetings.map((m) => (
            <div
              key={m.id}
              className="vaak-card"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1.25rem 1.75rem',
                flexWrap: 'wrap',
                gap: '1rem',
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '220px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)' }}>
                    {m.title || `Meeting ${m.id}`}
                  </h3>
                  {m.active && (
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 800,
                        color: 'var(--status-online)',
                        backgroundColor: 'rgba(16, 185, 129, 0.15)',
                        border: '1px solid rgba(16, 185, 129, 0.35)',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}
                    >
                      Active
                    </span>
                  )}
                </div>

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    fontSize: '0.8rem',
                    color: 'var(--text-muted)',
                    flexWrap: 'wrap',
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Calendar size={14} />
                    {new Date(m.started_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </span>
                  <span>&bull;</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={14} />
                    {new Date(m.started_at).toLocaleTimeString(undefined, {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                  <span>&bull;</span>
                  <span>Duration: {formatDuration(m.duration_s)}</span>
                  <span>&bull;</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Users size={14} />
                    {m.participant_count || 1} participant{m.participant_count !== 1 ? 's' : ''}
                  </span>
                  <span>&bull;</span>
                  <span style={{ fontWeight: 600 }}>Role: {m.role === 'host' ? 'Host' : 'Guest'}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {m.active ? (
                  <button
                    onClick={() => navigate(`/m/${m.id}`)}
                    className="btn-primary"
                    style={{ padding: '0.6rem 1.2rem', fontSize: '0.88rem' }}
                  >
                    <RotateCcw size={15} />
                    <span>Rejoin</span>
                  </button>
                ) : (
                  <button
                    onClick={() => navigate(`/m/${m.id}`)}
                    className="btn-secondary"
                    style={{ padding: '0.6rem 1.2rem', fontSize: '0.88rem' }}
                  >
                    <span>Lobby</span>
                    <ArrowRight size={14} />
                  </button>
                )}

                <button
                  onClick={(e) => handleDeleteItem(m.id, e)}
                  disabled={deletingId === m.id}
                  className="btn-icon"
                  title="Remove from history"
                  aria-label="Remove from history"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}

          {nextCursor && (
            <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
              <button
                onClick={() => fetchMeetings(nextCursor)}
                className="btn-secondary"
              >
                Load More Meetings
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
