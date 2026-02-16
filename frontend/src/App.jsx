import { useEffect, useRef, useState } from 'react';
import GoogleAuth from './components/GoogleAuth.jsx';
import ProcessPricing from './components/ProcessPricing.jsx';
import Settings from './components/Settings.jsx';
import prozoLogo from '../Prozo_logo.png';

export default function App() {
  const [token, setToken] = useState(null);
  const [userInfo, setUserInfo] = useState(null);
  const [meLoading, setMeLoading] = useState(false);
  const [accessDenied, setAccessDenied] = useState(false);
  const [tab, setTab] = useState('process');
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);

  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') return saved;
    try {
      return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch { return 'light'; }
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    if (!showUserMenu) return;
    const handler = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) setShowUserMenu(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showUserMenu]);

  const getBase = () => {
    const origin = window.location.origin;
    const basePath = (import.meta.env.BASE_URL || '/');
    return origin + (basePath.endsWith('/') ? basePath.slice(0, -1) : basePath);
  };

  // Check saved token on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('id_token');
    if (savedToken) {
      setToken(savedToken);
      try {
        const payload = JSON.parse(atob(savedToken.split('.')[1]));
        setUserInfo({ name: payload.name, email: payload.email, picture: payload.picture });
      } catch { }

      // Verify with backend
      setMeLoading(true);
      (async () => {
        try {
          const r = await fetch(`${getBase()}/api/me`, {
            headers: { Authorization: `Bearer ${savedToken}` }
          });
          if (r.ok) {
            setAccessDenied(false);
          } else {
            setAccessDenied(true);
          }
        } catch {
          // Network error - allow offline usage
        } finally {
          setMeLoading(false);
        }
      })();
    }
  }, []);

  const handleSignIn = (newToken) => {
    setToken(newToken);
    try {
      const payload = JSON.parse(atob(newToken.split('.')[1]));
      setUserInfo({ name: payload.name, email: payload.email, picture: payload.picture });
      setAccessDenied(false);
    } catch { }
  };

  const handleLogout = () => {
    localStorage.removeItem('id_token');
    setToken(null);
    setUserInfo(null);
    setShowUserMenu(false);
    try { window.google?.accounts?.id?.disableAutoSelect(); } catch { }
  };

  // Sign-in page
  if (!token) {
    return (
      <div className="signin-container">
        <div style={{ position: 'absolute', top: 16, right: 16 }}>
          <label className="theme-switch">
            <input type="checkbox" checked={theme === 'dark'} onChange={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} />
            <span className="theme-slider" />
            <span className="theme-label">{theme === 'dark' ? 'Dark' : 'Light'}</span>
          </label>
        </div>
        <div className="card signin-card">
          <img src={prozoLogo} alt="Prozo" className="signin-logo" />
          <h2 className="signin-title">D2C Pricing Automation</h2>
          <GoogleAuth onSignedIn={handleSignIn} isSignedIn={false} userInfo={null} />
        </div>
      </div>
    );
  }

  // Loading state
  if (meLoading) {
    return (
      <div className="signin-container">
        <div className="flex flex-col items-center gap-3">
          <div className="spinner" style={{ width: 36, height: 36 }} />
          <p className="text-muted">Verifying access...</p>
        </div>
      </div>
    );
  }

  // Access denied
  if (accessDenied) {
    return (
      <div className="signin-container">
        <div className="card signin-card">
          <h2 style={{ color: 'var(--danger)' }}>Access Denied</h2>
          <p className="text-muted">You do not have access to this application.</p>
          <button className="btn btn-outline mt-3" onClick={handleLogout}>Sign Out</button>
        </div>
      </div>
    );
  }

  // Authenticated app
  return (
    <div>
      {/* Header */}
      <div className="app-header">
        <div className="app-header-inner">
          <div className="header-left">
            <img src={prozoLogo} alt="Prozo" className="header-logo" />
            <span className="header-title">D2C Pricing Automation</span>
          </div>
          <div className="header-right">
            <label className="theme-switch">
              <input type="checkbox" checked={theme === 'dark'} onChange={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} />
              <span className="theme-slider" />
              <span className="theme-label">{theme === 'dark' ? 'Dark' : 'Light'}</span>
            </label>
            <div style={{ position: 'relative' }} ref={userMenuRef}>
              <div onClick={() => setShowUserMenu(!showUserMenu)}>
                <GoogleAuth onSignedIn={handleSignIn} isSignedIn={true} userInfo={userInfo} />
              </div>
              {showUserMenu && (
                <div className="user-menu">
                  <div style={{ padding: '10px 18px', borderBottom: '1px solid var(--border)' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{userInfo?.name}</div>
                    <div className="text-xs text-muted">{userInfo?.email}</div>
                  </div>
                  <button onClick={() => { setTab('settings'); setShowUserMenu(false); }}>Settings</button>
                  <button onClick={handleLogout} style={{ color: 'var(--danger)' }}>Sign Out</button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Content area */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 16px' }}>
        {/* Tabs */}
        <div className="tabs">
          <button className={`tab-btn ${tab === 'process' ? 'active' : ''}`} onClick={() => setTab('process')}>
            Process Pricing
          </button>
          <button className={`tab-btn ${tab === 'settings' ? 'active' : ''}`} onClick={() => setTab('settings')}>
            Settings
          </button>
        </div>

        {/* Page content */}
        <div style={{ paddingTop: 20, paddingBottom: 32 }}>
          {tab === 'process' && <ProcessPricing token={token} />}
          {tab === 'settings' && <Settings token={token} />}
        </div>
      </div>
    </div>
  );
}
