import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from './context/AuthContext';

/**
 * GoogleAuth Component (Production GIS Sign-In)
 * Uses official Google Identity Services ("Sign in with Google" ID token).
 * Strict production mode: No simulated or demo logins.
 */
export function GoogleAuth({ onAuthenticated }) {
  const { signInWithGoogle, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTarget = searchParams.get('redirect') || '/';

  const googleBtnRef = useRef(null);
  const [authError, setAuthError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (user && onAuthenticated) {
      onAuthenticated(user);
    }
  }, [user, onAuthenticated]);

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

    const handleCredentialResponse = async (response) => {
      try {
        setIsSubmitting(true);
        setAuthError(null);
        const loggedUser = await signInWithGoogle(response.credential);
        if (onAuthenticated) onAuthenticated(loggedUser);
        navigate(redirectTarget, { replace: true });
      } catch (err) {
        setAuthError(err.message || 'Authentication failed. Please try again.');
      } finally {
        setIsSubmitting(false);
      }
    };

    if (window.google?.accounts?.id && googleBtnRef.current) {
      if (clientId) {
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: handleCredentialResponse,
        });

        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: 'filled_black',
          size: 'large',
          shape: 'pill',
          text: 'signin_with',
          width: 280,
        });
      }
    }
  }, [signInWithGoogle, onAuthenticated, navigate, redirectTarget]);

  // Dev-only fallback when VITE_API_MOCK=1
  const isMockDev = import.meta.env.DEV && import.meta.env.VITE_API_MOCK === '1';
  const handleDevLogin = async (name, email, lang) => {
    setIsSubmitting(true);
    setAuthError(null);
    try {
      const loggedUser = await signInWithGoogle({
        name,
        email,
        display_name: name,
        default_lang: lang,
      });
      if (onAuthenticated) onAuthenticated(loggedUser);
      navigate(redirectTarget, { replace: true });
    } catch (err) {
      setAuthError(err.message || 'Dev login failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        width: '100vw',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#090809',
        color: '#E8E2E8',
        padding: '1.5rem',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '460px',
          padding: '2.5rem',
          backgroundColor: '#171019',
          border: '1px solid rgba(162, 143, 165, 0.25)',
          borderRadius: '24px',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.8), 0 0 20px rgba(112, 86, 117, 0.12)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          position: 'relative',
          zIndex: 10,
        }}
      >
        <div style={{ marginBottom: '1.5rem' }}>
          <img
            src="/vaak_logo.png"
            alt="VAAK"
            style={{
              height: '68px',
              width: 'auto',
              objectFit: 'contain',
              marginBottom: '10px',
              filter: 'drop-shadow(0 6px 16px rgba(162, 143, 165, 0.25))',
            }}
            onError={(e) => {
              e.currentTarget.style.display = 'none';
            }}
          />
          <h1
            style={{
              fontFamily: "'Outfit', sans-serif",
              fontSize: '2.1rem',
              fontWeight: 800,
              letterSpacing: '0.18em',
              color: '#E8E2E8',
              lineHeight: 1.1,
            }}
          >
            VAAK
          </h1>
          <p
            style={{
              color: '#A28FA5',
              fontSize: '0.85rem',
              marginTop: '6px',
              letterSpacing: '0.04em',
              fontWeight: 500,
            }}
          >
            Real-Time Multilingual Video Conferencing
          </p>
        </div>

        {authError && (
          <div
            style={{
              width: '100%',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#fca5a5',
              padding: '10px 14px',
              borderRadius: '10px',
              fontSize: '0.82rem',
              marginBottom: '1.25rem',
              textAlign: 'left',
            }}
          >
            {authError}
          </div>
        )}

        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', margin: '1rem 0' }}>
          <div ref={googleBtnRef} style={{ minHeight: '44px' }} />

          {!import.meta.env.VITE_GOOGLE_CLIENT_ID && !isMockDev && (
            <p style={{ fontSize: '0.78rem', color: '#705675', maxWidth: '320px' }}>
              Requires <code>VITE_GOOGLE_CLIENT_ID</code> in production.
            </p>
          )}

          {isMockDev && (
            <div
              style={{
                width: '100%',
                marginTop: '1.25rem',
                paddingTop: '1.25rem',
                borderTop: '1px solid rgba(162, 143, 165, 0.18)',
              }}
            >
              <div
                style={{
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: '#705675',
                  marginBottom: '10px',
                  fontWeight: 700,
                }}
              >
                Development Test Profiles
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => handleDevLogin('Asha Rao', 'asha.rao@vaak.ai', 'hi')}
                  style={{
                    padding: '8px 12px',
                    backgroundColor: '#211526',
                    border: '1px solid rgba(162, 143, 165, 0.25)',
                    borderRadius: '8px',
                    color: '#E8E2E8',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Asha (Hindi)
                </button>
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => handleDevLogin('Vikram Sharma', 'vikram.s@vaak.ai', 'kn')}
                  style={{
                    padding: '8px 12px',
                    backgroundColor: '#211526',
                    border: '1px solid rgba(162, 143, 165, 0.25)',
                    borderRadius: '8px',
                    color: '#E8E2E8',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Vikram (Kannada)
                </button>
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            marginTop: '2rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid rgba(162, 143, 165, 0.12)',
            fontSize: '0.75rem',
            color: '#705675',
            display: 'flex',
            gap: '16px',
          }}
        >
          <a
            href="https://vaak.ai/privacy"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#A28FA5', textDecoration: 'underline' }}
          >
            Privacy Policy
          </a>
          <span>&bull;</span>
          <a
            href="https://vaak.ai/terms"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#A28FA5', textDecoration: 'underline' }}
          >
            Terms of Service
          </a>
        </div>
      </div>
    </div>
  );
}
