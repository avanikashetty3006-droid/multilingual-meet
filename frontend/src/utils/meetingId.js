/**
 * Utilities for meeting ID generation, parsing and validation.
 * Expected format: xxx-xxxx-xxx (10 lowercase letters/digits, unguessable, hyphenated).
 */

const MEETING_ID_REGEX = /^[a-z0-9]{3}-[a-z0-9]{4}-[a-z0-9]{3}$/i;
const UNHYPHENATED_REGEX = /^[a-z0-9]{10}$/i;

/**
 * Generate a random, unguessable meeting ID in format 'abc-defg-hij'.
 */
export function generateMeetingId() {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  const getRandom = (len) => {
    let result = '';
    const array = new Uint8Array(len);
    if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
      crypto.getRandomValues(array);
      for (let i = 0; i < len; i++) {
        result += chars[array[i] % chars.length];
      }
    } else {
      for (let i = 0; i < len; i++) {
        result += chars[Math.floor(Math.random() * chars.length)];
      }
    }
    return result;
  };

  return `${getRandom(3)}-${getRandom(4)}-${getRandom(3)}`;
}

/**
 * Parse an entered string which could be a raw ID ('abc-defg-hij'),
 * an unhyphenated string ('abcdefghij'), or a full URL ('https://site/m/abc-defg-hij').
 * Returns the normalized ID or null if invalid.
 */
export function parseMeetingId(input) {
  if (!input || typeof input !== 'string') return null;
  const trimmed = input.trim();

  // If it's a URL
  try {
    if (trimmed.includes('/m/')) {
      const match = trimmed.match(/\/m\/([a-z0-9-]+)/i);
      if (match && match[1]) {
        return normalizeMeetingId(match[1]);
      }
    }
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      const url = new URL(trimmed);
      const segments = url.pathname.split('/').filter(Boolean);
      const last = segments[segments.length - 1];
      if (last) return normalizeMeetingId(last);
    }
  } catch (e) {
    // Not a valid URL, continue to string checks
  }

  return normalizeMeetingId(trimmed);
}

/**
 * Normalize meeting ID into standard hyphenated format 'xxx-xxxx-xxx'.
 */
export function normalizeMeetingId(raw) {
  if (!raw) return null;
  const clean = raw.toLowerCase().trim().replace(/[^a-z0-9-]/g, '');

  if (MEETING_ID_REGEX.test(clean)) {
    return clean;
  }

  // Handle unhyphenated 10 characters
  const pure = clean.replace(/-/g, '');
  if (UNHYPHENATED_REGEX.test(pure)) {
    return `${pure.slice(0, 3)}-${pure.slice(3, 7)}-${pure.slice(7, 10)}`;
  }

  // Accept short custom rooms like "room-alpha" if between 4 and 20 chars
  if (/^[a-z0-9]{2,6}(-[a-z0-9]{2,6}){1,3}$/i.test(clean) && clean.length <= 20) {
    return clean;
  }

  return null;
}

/**
 * Check if a meeting ID is valid.
 */
export function isValidMeetingId(id) {
  return normalizeMeetingId(id) !== null;
}
