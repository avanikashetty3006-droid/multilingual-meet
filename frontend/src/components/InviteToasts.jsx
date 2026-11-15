import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Video } from 'lucide-react';
import { wsUrl } from '../utils/wsUrl';
import { USER_EVENT, addToast, backoffMs, parseUserEvent, toastFromInvite } from '../utils/userEvents';

/**
 * Owns the ONE /ws/user socket of this tab (the server allows 5 per user), reconnects with backoff,
 * re-broadcasts every event as a window CustomEvent (FriendsView listens to it for presence), and shows
 * a toast with a Join button when a friend invites you.
 */
export function InviteToasts() {
  const navigate = useNavigate();
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  useEffect(() => {
    if (import.meta.env.VITE_API_MOCK === '1') return undefined; // mock dev mode has no server
    let ws = null;
    let attempt = 0;
    let stopped = false;
    let retryTimer = null;

    const connect = () => {
      if (stopped) return;
      try {
        ws = new WebSocket(wsUrl('/ws/user', import.meta.env.VITE_CALL_SERVER_URL || ''));
      } catch {
        return;
      }
      ws.onopen = () => { attempt = 0; };
      ws.onmessage = (ev) => {
        const msg = parseUserEvent(ev.data);
        if (!msg) return;
        window.dispatchEvent(new CustomEvent(USER_EVENT, { detail: msg }));
        const toast = toastFromInvite(msg);
        if (toast) {
          setToasts((prev) => addToast(prev, toast));
          clearTimeout(timers.current[toast.id]);
          timers.current[toast.id] = setTimeout(() => dismiss(toast.id), 30000);
        }
      };
      ws.onclose = (ev) => {
        if (stopped || ev.code === 4401 || ev.code === 4403) return; // signed out / blocked: do not hammer the server
        retryTimer = setTimeout(connect, backoffMs(attempt++));
      };
    };

    const dismiss = (id) => setToasts((prev) => prev.filter((t) => t.id !== id));
    connect();
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      Object.values(timers.current).forEach(clearTimeout);
      if (ws) ws.close();
    };
  }, []);

  const dismiss = (id) => {
    clearTimeout(timers.current[id]);
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  if (toasts.length === 0) return null;
  return (
    <div className="invite-toasts" role="region" aria-label="Meeting invitations" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="invite-toast">
          <Video size={18} aria-hidden="true" />
          <span className="invite-toast-text">{t.text}</span>
          <button
            className="btn-primary invite-toast-join"
            onClick={() => { dismiss(t.id); navigate(`/m/${encodeURIComponent(t.meetingId)}`); }}
          >
            Join
          </button>
          <button className="btn-icon" aria-label="Dismiss invitation" onClick={() => dismiss(t.id)}>
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
