import React, { Suspense } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { LogoReveal } from './LogoReveal';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AppShell } from './components/AppShell';

// Views
import { SignInView } from './views/SignInView';
import { HomeView } from './views/HomeView';
import { MeetingsView } from './views/MeetingsView';
import { FriendsView } from './views/FriendsView';
import { SettingsView } from './views/SettingsView';
import { LobbyView } from './views/LobbyView';

/**
 * Route protection wrapper.
 * Deep links preserve target path via query parameter ?redirect=
 */
function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          height: '100vh',
          width: '100vw',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#090809',
          color: '#A28FA5',
          fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
          fontSize: '0.92rem',
        }}
      >
        Initializing VAAK session...
      </div>
    );
  }

  if (!user) {
    return <Navigate to={`/signin?redirect=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }

  return children;
}

export default function App() {
  const { showIntro, markIntroCompleted } = useAuth();

  return (
    <ErrorBoundary>
      {/* Cinematic Logo Reveal shown once per session after sign in */}
      {showIntro && <LogoReveal onComplete={markIntroCompleted} />}

      <Suspense
        fallback={
          <div
            style={{
              display: 'flex',
              height: '100vh',
              width: '100vw',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#090809',
              color: '#A28FA5',
            }}
          >
            Loading...
          </div>
        }
      >
        <Routes>
          {/* Public Sign-In Route */}
          <Route path="/signin" element={<SignInView />} />

          {/* Deep link lobby / conference screen */}
          <Route
            path="/m/:id"
            element={
              <RequireAuth>
                <LobbyView />
              </RequireAuth>
            }
          />

          {/* Authenticated App Shell Routes */}
          <Route
            path="/"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<HomeView />} />
            <Route path="meetings" element={<MeetingsView />} />
            <Route path="friends" element={<FriendsView />} />
            <Route path="settings" element={<SettingsView />} />
          </Route>

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
