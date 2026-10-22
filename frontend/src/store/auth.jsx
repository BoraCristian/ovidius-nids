import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiGet, apiPost, setAuthToken } from '../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('nids_token') || '');
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    setAuthToken(token);
    if (!token) { setUser(null); setBooting(false); return; }
    apiGet('/api/auth/me')
      .then(setUser)
      .catch(() => { setToken(''); setUser(null); sessionStorage.removeItem('nids_token'); })
      .finally(() => setBooting(false));
  }, [token]);

  const login = useCallback(async (username, password) => {
    const form = new URLSearchParams();
    form.set('username', username);
    form.set('password', password);

    // The backend's lifespan does init_db → seed_admin → reload_engine →
    // start simulator before serving traffic, but on a very cold boot the
    // first POST can still race that pipeline and come back as 500/503.
    // We transparently retry transient server errors (NOT 401/403) twice
    // with a short backoff so the user doesn't have to mash "Sign in".
    let lastErr;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const res = await apiPost('/api/auth/login', form, {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        });
        sessionStorage.setItem('nids_token', res.access_token);
        setToken(res.access_token);
        return;
      } catch (e) {
        lastErr = e;
        const transient = e?.status === 500 || e?.status === 502
          || e?.status === 503 || e?.status === 504
          || e?.status === undefined;          // network failure
        if (!transient) throw e;               // 401/403 etc — fail fast
        await new Promise((r) => setTimeout(r, 400 * (attempt + 1)));
      }
    }
    throw lastErr;
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem('nids_token');
    setToken('');
    setUser(null);
  }, []);

  const value = useMemo(() => ({ token, user, booting, login, logout }), [token, user, booting, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
