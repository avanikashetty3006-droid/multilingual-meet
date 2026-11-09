import React, { useState } from 'react';

export function GoogleAuth({ onAuthenticated }) {
  const [email, setEmail] = useState('demo.speaker@vaak.internal');
  const [name, setName] = useState('Demo Speaker');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const demoAccounts = [
    { name: 'Speaker 1 (English)', email: 'speaker.en@vaak.internal', avatar: 'EN', lang: 'en' },
    { name: 'Speaker 2 (Hindi)', email: 'speaker.hi@vaak.internal', avatar: 'HI', lang: 'hi' },
    { name: 'Speaker 3 (Kannada)', email: 'speaker.kn@vaak.internal', avatar: 'KN', lang: 'kn' },
    { name: 'Speaker 4 (Tamil)', email: 'speaker.ta@vaak.internal', avatar: 'TA', lang: 'ta' },
  ];

  const handleSignIn = (selectedName, selectedEmail, selectedLang) => {
    setIsSubmitting(true);
    setTimeout(() => {
      const user = {
        name: selectedName || name,
        email: selectedEmail || email,
        avatar: (selectedName || name)
          .split(' ')
          .map((n) => n[0])
          .join('')
          .slice(0, 2)
          .toUpperCase(),
        lang: selectedLang || 'en',
        token: 'demo-token-' + Math.random().toString(36).substring(2, 10),
      };
      localStorage.setItem('vaak_user', JSON.stringify(user));
      setIsSubmitting(false);
      onAuthenticated(user);
    }, 400);
  };

  return (
    <div style={styles.container}>
      <div style={styles.glowTopLeft} />
      <div style={styles.glowBottomRight} />

      {/* Brand Header */}
      <div style={styles.header}>
        <div style={styles.badge}>
          <span style={styles.badgeDot}></span>
          <span>Real-Time Multilingual Video Conferencing</span>
        </div>

        <div style={styles.logoWrap}>
          <img
            src="/vaak_logo.png"
            alt="VAAK Logo"
            style={styles.logoImg}
          />
        </div>

        <p style={styles.headerSubtitle}>
          Connecting the world through languages, one conversation at a time.
        </p>
      </div>

      {/* Auth Card */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h2 style={styles.cardTitle}>VAAK Conference Access</h2>
          <p style={styles.cardSubtitle}>
            Select a participant profile to enter the multilingual room
          </p>
        </div>

        {/* Primary Demo Sign-in Button */}
        <button
          onClick={() => handleSignIn(name, email, 'en')}
          disabled={isSubmitting}
          style={styles.googleBtn}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#8C6E63')}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#D3A376')}
        >
          <svg style={styles.googleIcon} viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          <span style={styles.googleBtnText}>
            {isSubmitting ? 'Entering conference...' : 'Continue as Demo Speaker'}
          </span>
          <span style={styles.arrowIcon}>&rarr;</span>
        </button>

        <div style={styles.divider}>
          <span style={styles.dividerText}>Or choose simulated speaker</span>
        </div>

        {/* Quick Profile Selection */}
        <div style={styles.profileList}>
          {demoAccounts.map((account) => (
            <button
              key={account.email}
              onClick={() => handleSignIn(account.name, account.email, account.lang)}
              style={styles.profileRow}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 224, 178, 0.4)';
                e.currentTarget.style.borderColor = '#D3A376';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.borderColor = 'rgba(211, 163, 118, 0.4)';
              }}
            >
              <div style={styles.avatar}>{account.avatar}</div>
              <div style={styles.profileMeta}>
                <div style={styles.profileName}>{account.name}</div>
                <div style={styles.profileEmail}>{account.email}</div>
              </div>
              <span style={styles.langTag}>{account.lang.toUpperCase()}</span>
            </button>
          ))}
        </div>

        {/* Notice */}
        <div style={styles.securityFooter}>
          <span>Demo Session Mode • Production ready for Google Identity Services</span>
        </div>
      </div>

      <div style={styles.deptFooter}>
        Department of Artificial Intelligence &amp; Machine Learning
      </div>
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#FFF2DF',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '2rem 1rem',
    position: 'relative',
    overflow: 'hidden',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
  glowTopLeft: {
    position: 'absolute',
    top: '-80px',
    left: '-80px',
    width: '320px',
    height: '320px',
    borderRadius: '50%',
    backgroundColor: 'rgba(255, 224, 178, 0.6)',
    filter: 'blur(70px)',
    pointerEvents: 'none',
  },
  glowBottomRight: {
    position: 'absolute',
    bottom: '-80px',
    right: '-80px',
    width: '340px',
    height: '340px',
    borderRadius: '50%',
    backgroundColor: 'rgba(211, 163, 118, 0.4)',
    filter: 'blur(80px)',
    pointerEvents: 'none',
  },
  header: {
    textAlign: 'center',
    marginBottom: '1.75rem',
    zIndex: 1,
  },
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.35rem 0.85rem',
    borderRadius: '999px',
    backgroundColor: 'rgba(255, 224, 178, 0.8)',
    border: '1px solid rgba(211, 163, 118, 0.6)',
    color: '#3E2522',
    fontSize: '0.72rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '1rem',
  },
  badgeDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    backgroundColor: '#D3A376',
  },
  logoWrap: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '0.5rem',
  },
  logoImg: {
    height: '64px',
    width: 'auto',
    objectFit: 'contain',
    filter: 'drop-shadow(0 4px 10px rgba(62, 37, 34, 0.15))',
  },
  headerSubtitle: {
    color: '#8C6E63',
    fontSize: '0.88rem',
    fontWeight: 500,
    margin: 0,
  },
  card: {
    width: '100%',
    maxWidth: '440px',
    backgroundColor: 'rgba(255, 255, 255, 0.92)',
    backdropFilter: 'blur(12px)',
    borderRadius: '20px',
    border: '1px solid #FFE0B2',
    boxShadow: '0 12px 35px rgba(62, 37, 34, 0.12)',
    padding: '2rem',
    zIndex: 1,
  },
  cardHeader: {
    textAlign: 'center',
    marginBottom: '1.5rem',
  },
  cardTitle: {
    fontSize: '1.35rem',
    fontWeight: 800,
    color: '#3E2522',
    margin: '0 0 0.35rem 0',
  },
  cardSubtitle: {
    fontSize: '0.82rem',
    color: '#8C6E63',
    margin: 0,
    lineHeight: 1.4,
  },
  googleBtn: {
    width: '100%',
    padding: '0.85rem 1rem',
    backgroundColor: '#ffffff',
    border: '1px solid #D3A376',
    borderRadius: '12px',
    color: '#3E2522',
    fontWeight: 600,
    fontSize: '0.9rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.75rem',
    cursor: 'pointer',
    boxShadow: '0 2px 6px rgba(0, 0, 0, 0.05)',
    transition: 'all 0.2s ease',
  },
  googleIcon: {
    width: '20px',
    height: '20px',
    flexShrink: 0,
  },
  googleBtnText: {
    letterSpacing: '0.01em',
  },
  arrowIcon: {
    marginLeft: 'auto',
    color: '#8C6E63',
    fontWeight: 700,
  },
  divider: {
    position: 'relative',
    textAlign: 'center',
    margin: '1.5rem 0',
    borderTop: '1px solid #FFE0B2',
  },
  dividerText: {
    position: 'relative',
    top: '-0.7em',
    backgroundColor: '#ffffff',
    padding: '0 0.75rem',
    color: '#8C6E63',
    fontSize: '0.7rem',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontWeight: 700,
  },
  profileList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  profileRow: {
    width: '100%',
    padding: '0.65rem 0.85rem',
    borderRadius: '10px',
    border: '1px solid rgba(211, 163, 118, 0.4)',
    backgroundColor: 'transparent',
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'all 0.15s ease',
  },
  avatar: {
    width: '36px',
    height: '36px',
    borderRadius: '50%',
    backgroundColor: '#3E2522',
    color: '#FFF2DF',
    fontWeight: 700,
    fontSize: '0.78rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  profileMeta: {
    flex: 1,
    minWidth: 0,
  },
  profileName: {
    fontSize: '0.85rem',
    fontWeight: 700,
    color: '#3E2522',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  profileEmail: {
    fontSize: '0.72rem',
    color: '#8C6E63',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  langTag: {
    fontSize: '0.68rem',
    fontWeight: 700,
    padding: '0.15rem 0.5rem',
    borderRadius: '999px',
    backgroundColor: 'rgba(255, 224, 178, 0.7)',
    color: '#3E2522',
    border: '1px solid rgba(211, 163, 118, 0.5)',
  },
  securityFooter: {
    marginTop: '1.5rem',
    paddingTop: '1rem',
    borderTop: '1px solid rgba(255, 224, 178, 0.6)',
    textAlign: 'center',
    fontSize: '0.72rem',
    color: '#8C6E63',
    fontWeight: 600,
  },
  deptFooter: {
    marginTop: '1.25rem',
    fontSize: '0.75rem',
    color: '#8C6E63',
    fontWeight: 600,
    zIndex: 1,
  },
};
