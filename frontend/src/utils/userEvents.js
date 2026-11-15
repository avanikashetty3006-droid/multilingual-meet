/** Pure helpers for the /ws/user socket and the invite flow (unit-checked in tests/userEvents.check.mjs). */

export const USER_EVENT = 'vaak:user-event';

/** Parse one WebSocket text frame. Returns the message object or null (ignores 'pong' and junk). */
export function parseUserEvent(text) {
  if (typeof text !== 'string' || text[0] !== '{') return null;
  try {
    const msg = JSON.parse(text);
    return msg && typeof msg.type === 'string' ? msg : null;
  } catch {
    return null;
  }
}

/** Reconnect delay: 1s, 2s, 4s ... capped at 30s. */
export function backoffMs(attempt) {
  return Math.min(30000, 1000 * 2 ** Math.max(0, attempt));
}

/** Turn an `invite` event into a toast, or null when it is malformed. Only same-site /m/<id> links are trusted. */
export function toastFromInvite(msg) {
  if (!msg || msg.type !== 'invite' || typeof msg.meeting_id !== 'string') return null;
  const who = msg.from_user && typeof msg.from_user.display_name === 'string' ? msg.from_user.display_name : 'A friend';
  const title = typeof msg.title === 'string' && msg.title ? msg.title : 'a meeting';
  return { id: `${msg.meeting_id}:${msg.from_user?.id || ''}`, meetingId: msg.meeting_id, text: `${who} invited you to ${title}` };
}

/** Add a toast; the same meeting+sender replaces the older toast; at most 3 are kept. */
export function addToast(list, toast) {
  return [...list.filter((t) => t.id !== toast.id), toast].slice(-3);
}

/** From the history items, the meeting a friend should be invited to: the most recent ACTIVE one hosted or joined. */
export function pickActiveMeeting(items) {
  return (Array.isArray(items) ? items : []).find((m) => m && m.active) || null;
}
