import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { Siren, Search, RefreshCw } from 'lucide-react';
import { apiGet, apiPatch } from '../api/client.js';
import SeverityBadge from '../components/SeverityBadge.jsx';
import MethodBadge from '../components/MethodBadge.jsx';
import { useLive } from '../components/Layout.jsx';

const SEVERITIES = ['', 'low', 'medium', 'high', 'critical'];
const METHODS    = ['', 'signature', 'ml', 'hybrid'];
const STATUSES   = ['', 'new', 'triaged', 'closed'];

export default function Alerts() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ severity: '', method: '', status: '', q: '' });
  const { alerts: liveAlerts } = useLive();

  async function load() {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (f.severity) params.set('severity', f.severity);
      if (f.method)   params.set('method',   f.method);
      if (f.status)   params.set('status',   f.status);
      if (f.q)        params.set('q',        f.q);
      params.set('limit', '200');
      const data = await apiGet(`/api/alerts?${params.toString()}`);
      setRows(data);
    } finally {
      setBusy(false);
    }
  }

  // Re-fetch whenever a dropdown changes (instant) or the search box settles
  // for 300 ms (debounced so we don't spam the API on every keystroke).
  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.severity, f.method, f.status, f.q]);

  // Predicate for filtering live WS alerts client-side — the server already
  // filtered the initial `rows` so we only need to gate the newcomers.
  const liveMatches = (a) => {
    if (f.severity && a.severity !== f.severity) return false;
    if (f.method   && a.detection_method !== f.method) return false;
    if (f.status   && (a.status || 'new') !== f.status) return false;
    if (f.q) {
      const needle = f.q.toLowerCase();
      const hay = `${a.message || ''} ${a.rule_name || ''}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  };

  // Merge live WS alerts so table stays fresh without a refetch, but respect
  // the active filters so toggling "severity: high" actually hides the rest.
  const merged = useMemo(() => {
    const seen = new Set(rows.map(r => r.id));
    const prepended = liveAlerts
      .filter(a => !seen.has(a.id))
      .map(a => ({ ...a, status: a.status || 'new' }))
      .filter(liveMatches);
    return [...prepended, ...rows];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, liveAlerts, f.severity, f.method, f.status, f.q]);

  async function setStatus(id, status) {
    await apiPatch(`/api/alerts/${id}`, { status });
    setRows(rs => rs.map(r => r.id === id ? { ...r, status } : r));
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Siren className="w-6 h-6 text-cyan-400" /> Alerts
          </h1>
          <p className="text-slate-400 text-sm">All detections from signature and ML engines.</p>
        </div>
        <button onClick={load} className="btn btn-ghost" disabled={busy}>
          <RefreshCw className={`w-4 h-4 ${busy ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="card p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        <div className="md:col-span-2 relative">
          <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
          <input
            className="input pl-9"
            placeholder="Search messages…"
            value={f.q}
            onChange={e => setF({ ...f, q: e.target.value })}
          />
        </div>
        <select className="input" value={f.severity} onChange={e => setF({ ...f, severity: e.target.value })}>
          {SEVERITIES.map(s => <option key={s} value={s}>{s ? `severity: ${s}` : 'severity: any'}</option>)}
        </select>
        <select className="input" value={f.method} onChange={e => setF({ ...f, method: e.target.value })}>
          {METHODS.map(s => <option key={s} value={s}>{s ? `method: ${s}` : 'method: any'}</option>)}
        </select>
        <select className="input" value={f.status} onChange={e => setF({ ...f, status: e.target.value })}>
          {STATUSES.map(s => <option key={s} value={s}>{s ? `status: ${s}` : 'status: any'}</option>)}
        </select>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-navy-850 text-slate-400">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">Time</th>
              <th className="px-4 py-3 font-medium">Severity</th>
              <th className="px-4 py-3 font-medium">Method</th>
              <th className="px-4 py-3 font-medium">Rule</th>
              <th className="px-4 py-3 font-medium">Source</th>
              <th className="px-4 py-3 font-medium">Destination</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {merged.map((a) => (
              <tr key={a.id} className="border-t border-navy-800 hover:bg-navy-850/50">
                <td className="px-4 py-3 text-slate-300 whitespace-nowrap">
                  {a.ts ? format(new Date(a.ts), 'MMM d HH:mm:ss') : '—'}
                </td>
                <td className="px-4 py-3"><SeverityBadge value={a.severity} /></td>
                <td className="px-4 py-3"><MethodBadge value={a.detection_method} /></td>
                <td className="px-4 py-3">
                  <div className="text-slate-100">{a.rule_name || '—'}</div>
                  <div className="text-xs text-slate-500 truncate max-w-xs">{a.message}</div>
                </td>
                <td className="px-4 py-3"><span className="tag-mono">{a.src_ip}:{a.src_port}</span></td>
                <td className="px-4 py-3"><span className="tag-mono">{a.dst_ip}:{a.dst_port}</span></td>
                <td className="px-4 py-3">
                  <select
                    value={a.status}
                    onChange={e => setStatus(a.id, e.target.value)}
                    className="input !py-1"
                  >
                    <option value="new">new</option>
                    <option value="triaged">triaged</option>
                    <option value="closed">closed</option>
                  </select>
                </td>
                <td className="px-4 py-3">
                  <Link to={`/alerts/${a.id}`} className="text-cyan-400 hover:text-cyan-300 text-sm">Inspect →</Link>
                </td>
              </tr>
            ))}
            {!merged.length && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-500">No alerts match the current filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
