import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ShieldCheck, LogIn } from 'lucide-react';
import { apiGet } from '../api/client.js';
import { useAuth } from '../store/auth.jsx';

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [username, setU] = useState('');
  const [password, setP] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  // Demo convenience (pre-filled admin/admin + hint) only when the backend
  // runs with DEBUG=true; production builds show an empty form.
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    apiGet('/api/health')
      .then((h) => {
        if (!h?.debug) return;
        setDemoMode(true);
        setU((u) => u || 'admin');
        setP((p) => p || 'admin');
      })
      .catch(() => { /* backend still starting — keep the empty form */ });
  }, []);

  if (user) return <Navigate to="/" replace />;

  async function submit(e) {
    e.preventDefault();
    setErr(''); setBusy(true);
    try {
      await login(username, password);
      nav('/');
    } catch (e) {
      setErr(e.message || 'Login failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-6">
      <div className="max-w-md w-full card p-8 relative overflow-hidden">
        <div className="absolute -top-24 -right-24 w-60 h-60 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none" />
        <div className="flex items-center gap-3 mb-6">
          <div className="w-11 h-11 rounded-xl bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Ovidius NIDS</h1>
            <p className="text-slate-400 text-sm">Sign in to the SIEM console</p>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1">Username</label>
            <input className="input" value={username} onChange={e => setU(e.target.value)} autoFocus />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1">Password</label>
            <input type="password" className="input" value={password} onChange={e => setP(e.target.value)} />
          </div>
          {err && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">{err}</div>}
          <button type="submit" disabled={busy} className="btn btn-primary w-full justify-center">
            <LogIn className="w-4 h-4" /> {busy ? 'Signing in…' : 'Sign in'}
          </button>
          {demoMode && (
            <div className="text-xs text-slate-500 text-center">
              Default credentials: <code className="tag-mono">admin</code> / <code className="tag-mono">admin</code>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
