import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showIntro, setShowIntro] = useState(false);

  // Sync HTML data-theme attribute
  const applyTheme = useCallback((themeSetting) => {
    const root = document.documentElement;
    if (themeSetting === 'light') {
      root.setAttribute('data-theme', 'light');
    } else if (themeSetting === 'dark') {
      root.removeAttribute('data-theme');
    } else {
      // System preference
      const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (isDark) {
        root.removeAttribute('data-theme');
      } else {
        root.setAttribute('data-theme', 'light');
      }
    }
  }, []);

  // Check existing session on mount
  useEffect(() => {
    let mounted = true;
    const checkSession = async () => {
      try {
        const me = await api.user.getMe();
        if (mounted && me) {
          setUser(me);
          applyTheme(me.theme || 'dark');
        }
      } catch (err) {
        if (mounted) setUser(null);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    checkSession();
    return () => {
      mounted = false;
    };
  }, [applyTheme]);

  // Sign in with Google ID token
  const signInWithGoogle = useCallback(
    async (credential) => {
      setLoading(true);
      try {
        const loggedInUser = await api.auth.google(credential);
        setUser(loggedInUser);
        applyTheme(loggedInUser.theme || 'dark');

        // Check if intro has been seen this session
        const hasSeenIntro = sessionStorage.getItem('vaak_intro_seen');
        if (!hasSeenIntro) {
          setShowIntro(true);
        }
        return loggedInUser;
      } finally {
        setLoading(false);
      }
    },
    [applyTheme]
  );

  const markIntroCompleted = useCallback(() => {
    sessionStorage.setItem('vaak_intro_seen', 'true');
    setShowIntro(false);
  }, []);

  const replayIntro = useCallback(() => {
    sessionStorage.removeItem('vaak_intro_seen');
    setShowIntro(true);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch (e) {
      // Ignore network failures on logout
    } finally {
      setUser(null);
      sessionStorage.removeItem('vaak_intro_seen');
    }
  }, []);

  const updateProfile = useCallback(
    async (patch) => {
      const updated = await api.user.updateMe(patch);
      setUser(updated);
      if (patch.theme) applyTheme(patch.theme);
      return updated;
    },
    [applyTheme]
  );

  const deleteAccount = useCallback(async () => {
    await api.user.deleteMe();
    setUser(null);
    sessionStorage.removeItem('vaak_intro_seen');
  }, []);

  const value = {
    user,
    loading,
    showIntro,
    signInWithGoogle,
    markIntroCompleted,
    replayIntro,
    signOut,
    updateProfile,
    deleteAccount,
    applyTheme,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
