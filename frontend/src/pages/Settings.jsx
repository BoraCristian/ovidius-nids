import { useEffect, useState } from 'react';
import { Settings as SettingsIcon, KeyRound, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { apiGet, apiPost } from '../api/client.js';
import { useAuth } from '../store/auth.jsx';

export default function Settings() {
  const { user, logout } = useAuth();
  const [health, setHealth] = useState(null);

  // Change-password form state
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [okMsg, setOkMsg] = useState('');

  useEffect(() => {
    let alive = true;
    async function tick() {
      try { const h = await apiGet('/api/health'); if (alive) setHealth(h); } catch {}
    }
    tick();
    const id = setInterval(tick, 3000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  async function submitPassword(e) {
    e.preventDefault();
    setErr(''); setOkMsg('');
    if (next.length < 4) {
      setErr('New password must be at least 4 characters.');
      return;
    }
    if (next !== confirmPw) {
      setErr('New password and confirmation do not match.');
      return;
    }
    setBusy(true);
    try {
      await apiPost('/api/auth/change-password', {
        current_password: cur,
        new_password: next,
      });
      setCur(''); setNext(''); setConfirmPw('');
      setOkMsg('Password updated. You\'ll be signed out in a moment so you can sign back in.');
      setTimeout(() => logout(), 1500);
    } catch (e) {
      setErr(e.message || 'Could not update password.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <SettingsIcon className="w-6 h-6 text-cyan-400" /> Settings
        </h1>
        <p className="text-slate-400 text-sm">Account, engine status, and deployment reference.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* --- Account --- */}
        <div className="card p-5 lg:col-span-2 space-y-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <h2 className="font-semibold">Account</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <Info label="Signed in as" value={user?.username ?? '—'} />
            <Info label="Role"          value={user?.role ?? '—'} />
            <Info label="Status"        value={user?.is_active ? 'active' : 'disabled'} />
          </div>

          <div className="border-t border-navy-800 pt-4">
            <div className="flex items-center gap-2 mb-3">
              <KeyRound className="w-4 h-4 text-cyan-400" />
              <h3 className="font-semibold text-sm">Change password</h3>
            </div>
            <form onSubmit={submitPassword} className="space-y-3 max-w-md">
              <input
                type="password"
                className="input"
                placeholder="Current password"
                value={cur}
                onChange={e => setCur(e.target.value)}
                autoComplete="current-password"
                required
              />
              <input
                type="password"
                className="input"
                placeholder="New password (min. 4 characters)"
                value={next}
                onChange={e => setNext(e.target.value)}
                autoComplete="new-password"
                required
              />
              <input
                type="password"
                className="input"
                placeholder="Confirm new password"
                value={confirmPw}
                onChange={e => setConfirmPw(e.target.value)}
                autoComplete="new-password"
                required
              />
              {err && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
                  {err}
                </div>
              )}
              {okMsg && (
                <div className="text-sm text-green-300 bg-green-500/10 border border-green-500/30 rounded-lg px-3 py-2 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" /> {okMsg}
                </div>
              )}
              <button type="submit" className="btn btn-primary" disabled={busy}>
                <KeyRound className="w-4 h-4" /> {busy ? 'Saving…' : 'Update password'}
              </button>
            </form>
          </div>
        </div>

        {/* --- Engine status --- */}
        <div className="card p-5 space-y-3">
          <h2 className="font-semibold">Engine status</h2>
          <div className="space-y-2 text-sm">
            <Row k="Status"  v={health?.status ?? '—'} />
            <Row k="App"     v={health?.app    ?? '—'} />
            <Row k="Packets" v={(health?.packets ?? 0).toLocaleString()} />
            <Row k="Alerts"  v={(health?.alerts  ?? 0).toLocaleString()} />
            <Row k="PPS"     v={(health?.pps     ?? 0).toFixed(2)} />
          </div>
          <p className="text-xs text-slate-500 pt-2 border-t border-navy-800">
            Refreshed every 3 seconds from <code className="tag-mono">/api/health</code>.
          </p>
        </div>
      </div>

      {/* --- Deployment notes --- */}
      <div className="card p-5 text-sm space-y-3">
        <h2 className="font-semibold mb-1">Deployment configuration</h2>
        <p className="text-slate-300">
          Runtime knobs live in <code className="tag-mono">backend/.env</code>. Edit the file and
          restart the backend to apply changes.
        </p>
        <ul className="space-y-1.5 text-slate-300 list-disc list-inside">
          <li>
            <code className="tag-mono">SIMULATE_TRAFFIC=true</code> — generates synthetic
            benign + attack traffic so the dashboard always has something to show. Switch to{' '}
            <code className="tag-mono">false</code> and set{' '}
            <code className="tag-mono">SNIFFER_INTERFACE</code> to capture live packets.
          </li>
          <li>
            <code className="tag-mono">SNIFFER_BPF_FILTER</code> — Berkeley Packet Filter
            expression (e.g. <code className="tag-mono">tcp port 80</code>) applied at capture
            time when running live.
          </li>
          <li>
            <code className="tag-mono">SECRET_KEY</code> — JWT signing secret. Leave empty to
            have a random key generated on first boot; keep it out of version control.
          </li>
          <li>
            <code className="tag-mono">ACCESS_TOKEN_EXPIRE_MINUTES</code> — how long a login
            stays valid.
          </li>
          <li>
            Signature rules are stored in the <code className="tag-mono">rules</code> DB table
            (editable in <strong>Rules</strong>) and seeded from{' '}
            <code className="tag-mono">backend/data/rules/default_rules.yaml</code> on first
            boot. Edits from the UI take effect immediately — no restart needed.
          </li>
          <li>
            Trained ML models are persisted to{' '}
            <code className="tag-mono">backend/data/models/*.joblib</code>; the active model is
            re-loaded on backend restart.
          </li>
        </ul>
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="border border-navy-800 rounded-lg px-3 py-2">
      <div className="text-xs uppercase text-slate-400">{label}</div>
      <div className="text-sm font-medium text-slate-100">{value}</div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-slate-400">{k}</span>
      <span className="text-slate-100 font-medium">{v}</span>
    </div>
  );
}
