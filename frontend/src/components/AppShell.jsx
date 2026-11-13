import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Home,
  Calendar,
  Users,
  Settings,
  LogOut,
  Video,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function AppShell() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate('/signin');
  };

  return (
    <div className="app-shell">
      {/* Desktop Left Sidebar */}
      <aside className="app-sidebar" aria-label="Main Navigation">
        {/* Brand Header */}
        <div className="sidebar-brand">
          <div className="brand-emblem-wrap">
            <img
              src="/vaak_logo.png"
              alt="VAAK Emblem"
              style={{ width: '26px', height: '26px', objectFit: 'contain' }}
              onError={(e) => {
                e.currentTarget.style.display = 'none';
              }}
            />
          </div>
          <div className="brand-text-block">
            <span className="brand-logo-text">VAAK</span>
            <span className="brand-logo-sub">Multilingual Meet</span>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="sidebar-nav">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            aria-label="Home"
          >
            <Home className="nav-icon" />
            <span>Home</span>
          </NavLink>

          <NavLink
            to="/meetings"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            aria-label="Meetings History"
          >
            <Calendar className="nav-icon" />
            <span>Meetings</span>
          </NavLink>

          <NavLink
            to="/friends"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            aria-label="Friends and Contacts"
          >
            <Users className="nav-icon" />
            <span>Friends</span>
          </NavLink>

          <NavLink
            to="/settings"
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            aria-label="Settings and Profile"
          >
            <Settings className="nav-icon" />
            <span>Settings</span>
          </NavLink>
        </nav>

        {/* User Profile Strip at Bottom */}
        <div className="sidebar-footer">
          <div className="user-profile-strip">
            {user?.picture ? (
              <img
                src={user.picture}
                alt={user.display_name || user.name || 'User'}
                className="user-avatar-img"
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="user-avatar-placeholder">
                {(user?.display_name || user?.name || 'U').charAt(0).toUpperCase()}
              </div>
            )}
            <div className="user-info-text">
              <div className="user-display-name">{user?.display_name || user?.name || 'Participant'}</div>
              <div className="user-email-text">{user?.email || ''}</div>
            </div>
            <button
              onClick={handleSignOut}
              className="btn-icon"
              title="Sign Out"
              aria-label="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="app-main" id="main-content">
        <Outlet />
      </main>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="mobile-nav-bar" aria-label="Mobile Navigation">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
        >
          <Home className="nav-icon" />
          <span>Home</span>
        </NavLink>

        <NavLink
          to="/meetings"
          className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
        >
          <Calendar className="nav-icon" />
          <span>Meetings</span>
        </NavLink>

        <NavLink
          to="/friends"
          className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
        >
          <Users className="nav-icon" />
          <span>Friends</span>
        </NavLink>

        <NavLink
          to="/settings"
          className={({ isActive }) => `mobile-nav-item ${isActive ? 'active' : ''}`}
        >
          <Settings className="nav-icon" />
          <span>Settings</span>
        </NavLink>
      </nav>
    </div>
  );
}
