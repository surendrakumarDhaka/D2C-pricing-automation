import { useEffect, useRef, useState } from 'react';

export default function GoogleAuth({ onSignedIn, isSignedIn, userInfo }) {
  const btnRef = useRef(null);
  const [runtimeClientId, setRuntimeClientId] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const origin = window.location.origin;
        const basePath = (import.meta.env.BASE_URL || '/');
        const base = origin + (basePath.endsWith('/') ? basePath.slice(0, -1) : basePath);
        const r = await fetch(`${base}/api/config`);
        if (r.ok) {
          const j = await r.json();
          if (j?.googleClientId) setRuntimeClientId(j.googleClientId);
        }
      } catch {}
    })();

    const existing = document.getElementById('google-gis');
    if (existing) { init(); return; }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.id = 'google-gis';
    script.onload = () => init();
    document.head.appendChild(script);
  }, [runtimeClientId]);

  const init = () => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || runtimeClientId;
    if (!clientId || !window.google) return;
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: (response) => {
        const token = response?.credential;
        if (token) {
          try {
            const payload = JSON.parse(atob(token.split('.')[1] || '')) || {};
            const email = payload?.email || '';
            if (!email.endsWith('@prozo.com')) {
              try { window.google.accounts.id.disableAutoSelect(); } catch (e) {}
              alert('Please sign in with your @prozo.com account.');
              return;
            }
          } catch (e) {}
          localStorage.setItem('id_token', token);
          onSignedIn(token);
        }
      },
      auto_select: true,
      itp_support: true,
      context: 'signin',
      hosted_domain: 'prozo.com',
    });
    if (btnRef.current) {
      window.google.accounts.id.renderButton(btnRef.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'signin_with',
        shape: 'rectangular',
      });
    }
  };

  if (isSignedIn && userInfo) {
    const displayName = userInfo.name || (userInfo.email ? userInfo.email.split('@')[0] : 'User');
    return (
      <span className="user-chip">
        {displayName}
      </span>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      {!(import.meta.env.VITE_GOOGLE_CLIENT_ID || runtimeClientId) && (
        <div className="message-warning" style={{ fontSize: 12, maxWidth: 320 }}>
          Set VITE_GOOGLE_CLIENT_ID in .env to enable Google Sign-In.
        </div>
      )}
      <div ref={btnRef} />
    </div>
  );
}
