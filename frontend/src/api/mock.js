/**
 * VAAK Mock API Layer (For Development Only - VITE_API_MOCK=1)
 * Completely excluded from production builds.
 */

import { generateMeetingId } from '../utils/meetingId';

const STORAGE_KEY_USER = 'vaak_mock_user';
const STORAGE_KEY_MEETINGS = 'vaak_mock_meetings';
const STORAGE_KEY_HISTORY = 'vaak_mock_history';
const STORAGE_KEY_FRIENDS = 'vaak_mock_friends';
const STORAGE_KEY_REQUESTS = 'vaak_mock_requests';

function load(key, defaultVal) {
  try {
    const val = localStorage.getItem(key);
    return val ? JSON.parse(val) : defaultVal;
  } catch (e) {
    return defaultVal;
  }
}

function save(key, val) {
  try {
    localStorage.setItem(key, JSON.stringify(val));
  } catch (e) {}
}

const DEFAULT_USER = {
  id: 'usr_asha_1',
  email: 'asha.rao@vaak.ai',
  name: 'Asha Rao',
  display_name: 'Asha Rao',
  picture: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
  default_lang: 'hi',
  mic_default: true,
  cam_default: true,
  subtitles_only: false,
  theme: 'dark',
};

const DEFAULT_FRIENDS = [
  {
    id: 'usr_vikram_2',
    email: 'vikram.s@vaak.ai',
    name: 'Vikram Sharma',
    display_name: 'Vikram Sharma',
    picture: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80',
    presence: 'online',
    default_lang: 'kn',
  },
  {
    id: 'usr_ananya_3',
    email: 'ananya.p@vaak.ai',
    name: 'Ananya Patel',
    display_name: 'Ananya Patel',
    picture: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80',
    presence: 'in_meeting',
    default_lang: 'hi',
  },
  {
    id: 'usr_rohan_4',
    email: 'rohan.iyer@vaak.ai',
    name: 'Rohan Iyer',
    display_name: 'Rohan Iyer',
    picture: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80',
    presence: 'offline',
    default_lang: 'ta',
  },
];

const DEFAULT_REQUESTS = [
  {
    id: 'req_101',
    from_user: {
      id: 'usr_priya_5',
      email: 'priya.das@vaak.ai',
      name: 'Priya Das',
      display_name: 'Priya Das',
      picture: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&auto=format&fit=crop&q=80',
    },
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    direction: 'inbound',
  },
];

const DEFAULT_HISTORY = [
  {
    id: 'vaak-arch-sync',
    title: 'VAAK Multilingual Engine Architecture',
    started_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    ended_at: new Date(Date.now() - 3600000 * 1.3).toISOString(),
    duration_s: 2520,
    participant_count: 4,
    role: 'host',
    active: false,
  },
  {
    id: 'nlp-eval-team',
    title: 'Indian Language MT Evaluation & Speech Quality',
    started_at: new Date(Date.now() - 86400000 * 1).toISOString(),
    ended_at: new Date(Date.now() - 86400000 * 1 + 1800000).toISOString(),
    duration_s: 1800,
    participant_count: 6,
    role: 'guest',
    active: false,
  },
];

export async function handleMockRequest(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const body = options.body ? JSON.parse(options.body) : {};

  // Artificial slight network delay for realistic responsiveness
  await new Promise((r) => setTimeout(r, 60));

  let currentUser = load(STORAGE_KEY_USER, DEFAULT_USER);
  let meetings = load(STORAGE_KEY_MEETINGS, {});
  let history = load(STORAGE_KEY_HISTORY, DEFAULT_HISTORY);
  let friends = load(STORAGE_KEY_FRIENDS, DEFAULT_FRIENDS);
  let requests = load(STORAGE_KEY_REQUESTS, DEFAULT_REQUESTS);

  // POST /v1/auth/google
  if (path === '/v1/auth/google' && method === 'POST') {
    currentUser = {
      ...DEFAULT_USER,
      name: body.name || DEFAULT_USER.name,
      display_name: body.display_name || body.name || DEFAULT_USER.name,
      email: body.email || DEFAULT_USER.email,
    };
    save(STORAGE_KEY_USER, currentUser);
    return { status: 200, data: currentUser };
  }

  // POST /v1/auth/logout
  if (path === '/v1/auth/logout' && method === 'POST') {
    localStorage.removeItem(STORAGE_KEY_USER);
    return { status: 200, data: { ok: true } };
  }

  // GET /v1/me
  if (path === '/v1/me' && method === 'GET') {
    if (!currentUser) {
      return { status: 401, error: { code: 'UNAUTHORIZED', message: 'Not authenticated' } };
    }
    return { status: 200, data: currentUser };
  }

  // PATCH /v1/me
  if (path === '/v1/me' && method === 'PATCH') {
    if (!currentUser) {
      return { status: 401, error: { code: 'UNAUTHORIZED', message: 'Not authenticated' } };
    }
    currentUser = { ...currentUser, ...body };
    save(STORAGE_KEY_USER, currentUser);
    return { status: 200, data: currentUser };
  }

  // DELETE /v1/me
  if (path === '/v1/me' && method === 'DELETE') {
    localStorage.removeItem(STORAGE_KEY_USER);
    localStorage.removeItem(STORAGE_KEY_HISTORY);
    localStorage.removeItem(STORAGE_KEY_FRIENDS);
    return { status: 200, data: { ok: true } };
  }

  // POST /v1/meetings
  if (path === '/v1/meetings' && method === 'POST') {
    const meetingId = generateMeetingId();
    const title = body.title?.trim() || `Meeting ${meetingId}`;
    const meeting = {
      id: meetingId,
      title,
      host_id: currentUser?.id || 'usr_asha_1',
      active: true,
      created_at: new Date().toISOString(),
      join_url: `${window.location.origin}/m/${meetingId}`,
    };
    meetings[meetingId] = meeting;
    save(STORAGE_KEY_MEETINGS, meetings);

    // Also add to history as host
    const histItem = {
      id: meetingId,
      title,
      started_at: new Date().toISOString(),
      ended_at: null,
      duration_s: 0,
      participant_count: 1,
      role: 'host',
      active: true,
    };
    history = [histItem, ...history.filter((h) => h.id !== meetingId)];
    save(STORAGE_KEY_HISTORY, history);

    return { status: 200, data: meeting };
  }

  // GET /v1/meetings/:id
  const meetingMatch = path.match(/^\/v1\/meetings\/([^/]+)$/);
  if (meetingMatch && method === 'GET') {
    const id = decodeURIComponent(meetingMatch[1]);
    const meeting = meetings[id] || {
      id,
      title: `Meeting ${id}`,
      active: true,
      host_id: 'usr_external',
      created_at: new Date().toISOString(),
      join_url: `${window.location.origin}/m/${id}`,
    };
    return { status: 200, data: meeting };
  }

  // POST /v1/meetings/:id/join
  const joinMatch = path.match(/^\/v1\/meetings\/([^/]+)\/join$/);
  if (joinMatch && method === 'POST') {
    const id = decodeURIComponent(joinMatch[1]);
    const livekitUrl = import.meta.env.VITE_LIVEKIT_URL || 'wss://livekit.example.com';
    const fakeToken = `dev-token-${Math.random().toString(36).substring(2, 12)}`;

    // Add/update history
    const existingHist = history.find((h) => h.id === id);
    if (!existingHist) {
      history = [
        {
          id,
          title: meetings[id]?.title || `Meeting ${id}`,
          started_at: new Date().toISOString(),
          ended_at: null,
          duration_s: 0,
          participant_count: 2,
          role: 'guest',
          active: true,
        },
        ...history,
      ];
      save(STORAGE_KEY_HISTORY, history);
    }

    return {
      status: 200,
      data: {
        livekit_token: fakeToken,
        livekit_url: livekitUrl,
      },
    };
  }

  // POST /v1/meetings/:id/end
  const endMatch = path.match(/^\/v1\/meetings\/([^/]+)\/end$/);
  if (endMatch && method === 'POST') {
    const id = decodeURIComponent(endMatch[1]);
    if (meetings[id]) {
      meetings[id].active = false;
      save(STORAGE_KEY_MEETINGS, meetings);
    }
    history = history.map((h) => (h.id === id ? { ...h, active: false, ended_at: new Date().toISOString() } : h));
    save(STORAGE_KEY_HISTORY, history);
    return { status: 200, data: { ok: true } };
  }

  // GET /v1/me/meetings
  if (path.startsWith('/v1/me/meetings') && method === 'GET') {
    return {
      status: 200,
      data: {
        items: history,
        next_cursor: null,
      },
    };
  }

  // DELETE /v1/me/meetings/:id
  const delHistMatch = path.match(/^\/v1\/me\/meetings\/([^/]+)$/);
  if (delHistMatch && method === 'DELETE') {
    const id = decodeURIComponent(delHistMatch[1]);
    history = history.filter((h) => h.id !== id);
    save(STORAGE_KEY_HISTORY, history);
    return { status: 200, data: { ok: true } };
  }

  // GET /v1/friends
  if (path === '/v1/friends' && method === 'GET') {
    return { status: 200, data: friends };
  }

  // GET /v1/friends/requests
  if (path === '/v1/friends/requests' && method === 'GET') {
    return { status: 200, data: requests };
  }

  // GET /v1/users/search?email=...
  if (path.startsWith('/v1/users/search') && method === 'GET') {
    const url = new URL(`http://localhost${path}`);
    const email = url.searchParams.get('email')?.toLowerCase();
    const directory = [
      ...friends,
      {
        id: 'usr_meera_6',
        email: 'meera.nair@vaak.ai',
        name: 'Meera Nair',
        display_name: 'Meera Nair',
        picture: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80',
        presence: 'online',
        default_lang: 'ml',
      },
      {
        id: 'usr_arjun_7',
        email: 'arjun.reddy@vaak.ai',
        name: 'Arjun Reddy',
        display_name: 'Arjun Reddy',
        picture: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=150&auto=format&fit=crop&q=80',
        presence: 'offline',
        default_lang: 'te',
      },
    ];

    const match = directory.find((u) => u.email.toLowerCase() === email);
    if (!match) {
      return { status: 404, error: { code: 'USER_NOT_FOUND', message: 'No user found with this exact email.' } };
    }
    return { status: 200, data: match };
  }

  // POST /v1/friends/requests
  if (path === '/v1/friends/requests' && method === 'POST') {
    const req = {
      id: `req_${Date.now()}`,
      to_email: body.email,
      created_at: new Date().toISOString(),
      direction: 'outbound',
    };
    requests = [req, ...requests];
    save(STORAGE_KEY_REQUESTS, requests);
    return { status: 200, data: req };
  }

  // POST /v1/friends/requests/:id/accept
  const acceptMatch = path.match(/^\/v1\/friends\/requests\/([^/]+)\/accept$/);
  if (acceptMatch && method === 'POST') {
    const reqId = decodeURIComponent(acceptMatch[1]);
    const req = requests.find((r) => r.id === reqId);
    if (req?.from_user) {
      friends = [
        ...friends,
        {
          ...req.from_user,
          presence: 'online',
          default_lang: 'hi',
        },
      ];
      save(STORAGE_KEY_FRIENDS, friends);
    }
    requests = requests.filter((r) => r.id !== reqId);
    save(STORAGE_KEY_REQUESTS, requests);
    return { status: 200, data: { ok: true } };
  }

  // POST /v1/friends/requests/:id/decline
  const declineMatch = path.match(/^\/v1\/friends\/requests\/([^/]+)\/decline$/);
  if (declineMatch && method === 'POST') {
    const reqId = decodeURIComponent(declineMatch[1]);
    requests = requests.filter((r) => r.id !== reqId);
    save(STORAGE_KEY_REQUESTS, requests);
    return { status: 200, data: { ok: true } };
  }

  // DELETE /v1/friends/:userId
  const delFriendMatch = path.match(/^\/v1\/friends\/([^/]+)$/);
  if (delFriendMatch && method === 'DELETE') {
    const userId = decodeURIComponent(delFriendMatch[1]);
    friends = friends.filter((f) => f.id !== userId);
    save(STORAGE_KEY_FRIENDS, friends);
    return { status: 200, data: { ok: true } };
  }

  // POST /v1/meetings/:id/invite
  const inviteMatch = path.match(/^\/v1\/meetings\/([^/]+)\/invite$/);
  if (inviteMatch && method === 'POST') {
    return { status: 200, data: { sent: true, recipient: body.user_id } };
  }

  return null;
}
