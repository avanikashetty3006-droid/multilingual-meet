/**
 * VAAK API Client (Contract A10)
 * Uses credentials: 'include' for httpOnly session cookie.
 * In development, hooks into the mock layer if VITE_API_MOCK === '1'.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export class ApiError extends Error {
  constructor(message, status = 500, code = 'INTERNAL_ERROR') {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

async function request(path, options = {}) {
  // If mock mode is enabled in dev, intercept request
  if (import.meta.env.DEV && import.meta.env.VITE_API_MOCK === '1') {
    const { handleMockRequest } = await import('./mock.js');
    const mockRes = await handleMockRequest(path, options);
    if (mockRes) {
      if (mockRes.error) {
        throw new ApiError(mockRes.error.message, mockRes.status || 400, mockRes.error.code);
      }
      return mockRes.data;
    }
  }

  const url = `${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const config = {
    ...options,
    headers,
    credentials: 'include', // essential for first-party httpOnly session cookies
  };

  let res;
  try {
    res = await fetch(url, config);
  } catch (err) {
    throw new ApiError('Network error. Unable to reach VAAK server.', 0, 'NETWORK_ERROR');
  }

  let body = null;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      body = await res.json();
    } catch (e) {
      body = null;
    }
  }

  if (!res.ok) {
    const message = body?.error?.message || `Request failed with status ${res.status}`;
    const code = body?.error?.code || `HTTP_${res.status}`;
    throw new ApiError(message, res.status, code);
  }

  return body;
}

export const api = {
  auth: {
    google: (credential) =>
      request('/v1/auth/google', {
        method: 'POST',
        body: JSON.stringify({ credential }),
      }),
    logout: () =>
      request('/v1/auth/logout', {
        method: 'POST',
      }),
  },

  user: {
    getMe: () => request('/v1/me', { method: 'GET' }),
    updateMe: (patch) =>
      request('/v1/me', {
        method: 'PATCH',
        body: JSON.stringify(patch),
      }),
    deleteMe: () => request('/v1/me', { method: 'DELETE' }),
  },

  meetings: {
    create: (title) =>
      request('/v1/meetings', {
        method: 'POST',
        body: JSON.stringify(title ? { title } : {}),
      }),
    get: (id) => request(`/v1/meetings/${encodeURIComponent(id)}`, { method: 'GET' }),
    join: (id, { display_name, lang }) =>
      request(`/v1/meetings/${encodeURIComponent(id)}/join`, {
        method: 'POST',
        body: JSON.stringify({ display_name, lang }),
      }),
    end: (id) =>
      request(`/v1/meetings/${encodeURIComponent(id)}/end`, {
        method: 'POST',
      }),
    getHistory: (cursor) =>
      request(`/v1/me/meetings${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`, {
        method: 'GET',
      }),
    deleteHistory: (id) =>
      request(`/v1/me/meetings/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      }),
    invite: (meetingId, userId) =>
      request(`/v1/meetings/${encodeURIComponent(meetingId)}/invite`, {
        method: 'POST',
        body: JSON.stringify({ user_id: userId }),
      }),
  },

  friends: {
    list: () => request('/v1/friends', { method: 'GET' }),
    getRequests: () => request('/v1/friends/requests', { method: 'GET' }),
    search: (email) =>
      request(`/v1/users/search?email=${encodeURIComponent(email.trim())}`, {
        method: 'GET',
      }),
    sendRequest: (email) =>
      request('/v1/friends/requests', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim() }),
      }),
    acceptRequest: (requestId) =>
      request(`/v1/friends/requests/${encodeURIComponent(requestId)}/accept`, {
        method: 'POST',
      }),
    declineRequest: (requestId) =>
      request(`/v1/friends/requests/${encodeURIComponent(requestId)}/decline`, {
        method: 'POST',
      }),
    remove: (userId) =>
      request(`/v1/friends/${encodeURIComponent(userId)}`, {
        method: 'DELETE',
      }),
  },
};
