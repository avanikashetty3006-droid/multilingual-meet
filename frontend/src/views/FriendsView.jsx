import React, { useState, useEffect } from 'react';
import {
  Users,
  UserPlus,
  Search,
  Check,
  X,
  Trash2,
  Share2,
  Mail,
  Send,
} from 'lucide-react';
import { api, ApiError } from '../api/client';

export function FriendsView() {
  const [activeTab, setActiveTab] = useState('friends'); // 'friends' | 'requests'
  const [friends, setFriends] = useState([]);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  // Search by exact email
  const [searchEmail, setSearchEmail] = useState('');
  const [searchResult, setSearchResult] = useState(null);
  const [searchError, setSearchError] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [sendSuccess, setSendSuccess] = useState('');

  const loadData = async () => {
    try {
      const [friendsList, reqsList] = await Promise.all([
        api.friends.list(),
        api.friends.getRequests(),
      ]);
      setFriends(Array.isArray(friendsList) ? friendsList : []);
      setRequests(Array.isArray(reqsList) ? reqsList : []);
    } catch (err) {
      console.warn('Failed to load friends data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();

    // Setup user WebSocket for presence events if server supports it
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${wsProto}//${wsHost}/ws/user`;

    let ws = null;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'presence') {
            setFriends((prev) =>
              prev.map((f) => (f.id === msg.user_id ? { ...f, presence: msg.presence } : f))
            );
          } else if (msg.type === 'friend_request' || msg.type === 'friend_accepted') {
            loadData();
          }
        } catch (e) {}
      };
    } catch (e) {}

    return () => {
      if (ws) ws.close();
    };
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchEmail.trim()) return;

    setIsSearching(true);
    setSearchError('');
    setSearchResult(null);
    setSendSuccess('');

    try {
      const user = await api.friends.search(searchEmail.trim());
      setSearchResult(user);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setSearchError('No user found with this exact email.');
      } else {
        setSearchError(err.message || 'Search failed.');
      }
    } finally {
      setIsSearching(false);
    }
  };

  const handleSendRequest = async (email) => {
    try {
      await api.friends.sendRequest(email);
      setSendSuccess('Friend request sent successfully!');
      setSearchResult(null);
      setSearchEmail('');
      loadData();
    } catch (err) {
      setSearchError(err.message || 'Failed to send request.');
    }
  };

  const handleAcceptRequest = async (id) => {
    try {
      await api.friends.acceptRequest(id);
      loadData();
    } catch (err) {
      alert('Failed to accept request.');
    }
  };

  const handleDeclineRequest = async (id) => {
    try {
      await api.friends.declineRequest(id);
      loadData();
    } catch (err) {
      alert('Failed to decline request.');
    }
  };

  const handleRemoveFriend = async (userId, name) => {
    if (!confirm(`Are you sure you want to remove ${name} from your friends?`)) return;

    try {
      await api.friends.remove(userId);
      setFriends((prev) => prev.filter((f) => f.id !== userId));
    } catch (err) {
      alert('Failed to remove friend.');
    }
  };

  const handleInviteToMeeting = (friend) => {
    const inviteLink = `${window.location.origin}`;
    navigator.clipboard.writeText(inviteLink);
    alert(`Meeting invite link copied for ${friend.display_name}! Send it via chat or email.`);
  };

  const inboundRequests = requests.filter((r) => r.direction === 'inbound');

  return (
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-title">Friends & Presence</h1>
        <p className="page-subtitle">
          See who is online, search colleagues by exact email, and manage meeting invites.
        </p>
      </header>

      {/* Search Bar Section */}
      <section className="vaak-card" style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <UserPlus size={18} color="var(--vaak-muted-lilac)" />
          <span>Add a Friend by Email</span>
        </h3>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '240px' }}>
            <input
              type="email"
              className="input-text"
              placeholder="Enter exact email (e.g. colleague@vaak.ai)"
              value={searchEmail}
              onChange={(e) => setSearchEmail(e.target.value)}
              required
              style={{ width: '100%' }}
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !searchEmail.trim()}
            className="btn-primary"
          >
            <Search size={16} />
            <span>{isSearching ? 'Searching...' : 'Find User'}</span>
          </button>
        </form>

        {searchError && (
          <div style={{ color: '#fca5a5', fontSize: '0.85rem', marginTop: '10px' }}>
            ⚠️ {searchError}
          </div>
        )}

        {sendSuccess && (
          <div style={{ color: 'var(--status-online)', fontSize: '0.85rem', marginTop: '10px' }}>
            ✓ {sendSuccess}
          </div>
        )}

        {/* Search Result Card */}
        {searchResult && (
          <div
            style={{
              marginTop: '1.25rem',
              padding: '1rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-glow)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {searchResult.picture ? (
                <img
                  src={searchResult.picture}
                  alt={searchResult.display_name}
                  style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover' }}
                />
              ) : (
                <div className="user-avatar-placeholder" style={{ width: '40px', height: '40px' }}>
                  {searchResult.display_name.charAt(0)}
                </div>
              )}
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                  {searchResult.display_name}
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  {searchResult.email}
                </div>
              </div>
            </div>

            <button
              onClick={() => handleSendRequest(searchResult.email)}
              className="btn-primary"
              style={{ padding: '0.55rem 1.1rem', fontSize: '0.85rem' }}
            >
              <Send size={14} />
              <span>Send Request</span>
            </button>
          </div>
        )}
      </section>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '12px', borderBottom: '1px solid var(--border-subtle)', marginBottom: '1.5rem' }}>
        <button
          onClick={() => setActiveTab('friends')}
          style={{
            padding: '0.75rem 1.25rem',
            fontWeight: 700,
            fontSize: '0.92rem',
            color: activeTab === 'friends' ? 'var(--vaak-warm-white)' : 'var(--text-muted)',
            borderBottom: activeTab === 'friends' ? '2px solid var(--vaak-muted-lilac)' : '2px solid transparent',
          }}
        >
          My Friends ({friends.length})
        </button>

        <button
          onClick={() => setActiveTab('requests')}
          style={{
            padding: '0.75rem 1.25rem',
            fontWeight: 700,
            fontSize: '0.92rem',
            color: activeTab === 'requests' ? 'var(--vaak-warm-white)' : 'var(--text-muted)',
            borderBottom: activeTab === 'requests' ? '2px solid var(--vaak-muted-lilac)' : '2px solid transparent',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>Pending Requests</span>
          {inboundRequests.length > 0 && (
            <span
              style={{
                backgroundColor: 'var(--vaak-soft-plum)',
                color: '#ffffff',
                padding: '2px 7px',
                borderRadius: '999px',
                fontSize: '0.72rem',
                fontWeight: 800,
              }}
            >
              {inboundRequests.length}
            </span>
          )}
        </button>
      </div>

      {/* Tab 1: Friends List */}
      {activeTab === 'friends' && (
        <div>
          {loading ? (
            <div style={{ color: 'var(--text-muted)', padding: '2rem 0' }}>Loading contacts...</div>
          ) : friends.length === 0 ? (
            <div className="vaak-card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.8rem' }}>👥</div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.5rem' }}>No Friends Added Yet</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                Search for someone using their exact email above to start connecting.
              </p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
              {friends.map((friend) => (
                <div
                  key={friend.id}
                  className="vaak-card"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '1.25rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ position: 'relative' }}>
                      {friend.picture ? (
                        <img
                          src={friend.picture}
                          alt={friend.display_name}
                          style={{ width: '44px', height: '44px', borderRadius: '50%', objectFit: 'cover' }}
                        />
                      ) : (
                        <div className="user-avatar-placeholder" style={{ width: '44px', height: '44px' }}>
                          {friend.display_name.charAt(0)}
                        </div>
                      )}
                      <span
                        className={`presence-dot ${friend.presence || 'offline'}`}
                        style={{ position: 'absolute', bottom: '1px', right: '1px', border: '2px solid var(--bg-surface)' }}
                      />
                    </div>

                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                        {friend.display_name}
                      </div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                        {friend.email}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--vaak-muted-lilac)', textTransform: 'capitalize', marginTop: '2px' }}>
                        {friend.presence === 'in_meeting' ? 'In a Meeting' : friend.presence || 'Offline'}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      onClick={() => handleInviteToMeeting(friend)}
                      className="btn-outline"
                      style={{ padding: '6px 10px', fontSize: '0.78rem' }}
                      title="Invite to meeting"
                    >
                      <Share2 size={13} />
                      <span>Invite</span>
                    </button>
                    <button
                      onClick={() => handleRemoveFriend(friend.id, friend.display_name)}
                      className="btn-icon"
                      style={{ width: '32px', height: '32px' }}
                      title="Remove friend"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Requests List */}
      {activeTab === 'requests' && (
        <div>
          {requests.length === 0 ? (
            <div className="vaak-card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.8rem' }}>✉️</div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.5rem' }}>No Pending Requests</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                You have no pending inbound or outbound friend requests.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {requests.map((req) => (
                <div
                  key={req.id}
                  className="vaak-card"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '1.25rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div className="user-avatar-placeholder" style={{ width: '40px', height: '40px' }}>
                      <Mail size={18} />
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>
                        {req.from_user?.display_name || req.to_email || 'User'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {req.direction === 'inbound' ? 'Sent you a friend request' : 'Friend request pending approval'}
                      </div>
                    </div>
                  </div>

                  {req.direction === 'inbound' ? (
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        onClick={() => handleAcceptRequest(req.id)}
                        className="btn-primary"
                        style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                      >
                        <Check size={14} />
                        <span>Accept</span>
                      </button>
                      <button
                        onClick={() => handleDeclineRequest(req.id)}
                        className="btn-danger"
                        style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                      >
                        <X size={14} />
                        <span>Decline</span>
                      </button>
                    </div>
                  ) : (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      Waiting for response
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
