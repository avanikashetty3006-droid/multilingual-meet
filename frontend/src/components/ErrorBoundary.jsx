import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('VAAK UI Error Boundary caught an error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleHome = () => {
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            width: '100vw',
            backgroundColor: '#090809',
            color: '#E8E2E8',
            padding: '2rem',
            textAlign: 'center',
            fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
          }}
        >
          <div
            style={{
              padding: '2.5rem',
              backgroundColor: '#171019',
              border: '1px solid rgba(162, 143, 165, 0.3)',
              borderRadius: '16px',
              maxWidth: '480px',
              boxShadow: '0 16px 40px rgba(0,0,0,0.6)',
            }}
          >
            <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>⚠️</div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.6rem' }}>
              Something unexpected occurred
            </h2>
            <p style={{ color: '#A28FA5', fontSize: '0.9rem', marginBottom: '1.5rem', lineHeight: 1.5 }}>
              The application encountered a rendering issue. Your data is safe. You can reload the page or return to the home screen.
            </p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button
                onClick={this.handleHome}
                style={{
                  padding: '0.75rem 1.4rem',
                  backgroundColor: '#211526',
                  border: '1px solid rgba(162, 143, 165, 0.3)',
                  borderRadius: '10px',
                  color: '#E8E2E8',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Go Home
              </button>
              <button
                onClick={this.handleReload}
                style={{
                  padding: '0.75rem 1.4rem',
                  background: 'linear-gradient(135deg, #302034, #49334D)',
                  border: '1px solid rgba(162, 143, 165, 0.4)',
                  borderRadius: '10px',
                  color: '#E8E2E8',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
