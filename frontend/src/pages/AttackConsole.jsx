import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Crosshair, Target, Zap, ServerCrash, Bug, KeyRound,
  RadioTower, Terminal, Info, CheckCircle2, Waves,
} from 'lucide-react';
import { apiGet, apiPost } from '../api/client.js';

/**
 * Maps an attack `kind` (from the backend catalog) to a lucide icon, so the
 * buttons stay visually distinct. Anything missing falls back to the bug
 * icon.
 */
const ICONS = {
  nmap:          Crosshair,
  ssh_brute:     KeyRound,
  icmp_flood:    ServerCrash,
  sqli:          Terminal,
  cmd_inject:    Terminal,
  reverse_shell: RadioTower,
};

export default function AttackConsole() {
  const [info, setInfo] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(null);          // kind currently firing
  const [err, setErr] = useState('');

  async function refreshInfo() {
    try {
      const i = await apiGet('/api/sim/info');
      setInfo(i);
    } catch (e) {
      setErr(e.message || 'Could not load simulator info');
    }
  }

  useEffect(() => {
    refreshInfo();
    const id = setInterval(refreshInfo, 4000);
    return () => clearInterval(id);
  }, []);

  async function fire(kind) {
    setBusy(kind); setErr('');
    try {
      const res = await apiPost('/api/sim/attack', { kind });
      setHistory((h) => [{ ...res, kindLabel: labelFor(kind) }, ...h].slice(0, 20));
      await refreshInfo();
    } catch (e) {
      setErr(e.message || `Failed to fire ${kind}`);
    } finally {
      setBusy(null);
    }
  }

  async function fireAll() {
    if (!info?.available_attacks) return;
    for (const a of info.available_attacks) {
      await fire(a.kind);
      // small spacing so the timeline shows them as distinct events
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  async function toggleBenign() {
    if (!info) return;
    try {
      const next = await apiPost('/api/sim/benign', { enabled: !info.benign_traffic });
      setInfo(next);
    } catch (e) {
      setErr(e.message || 'Could not toggle benign traffic');
    }
  }

  const labelFor = (kind) =>
    info?.available_attacks?.find((a) => a.kind === kind)?.label || kind;

  const offline = info && !info.enabled;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Zap className="w-6 h-6 text-amber-400" /> Attack Console
          </h1>
          <p className="text-slate-400 text-sm">
            Inject controlled attack traffic into the running simulator. Use
            this during demos to show the signature and ML engines reacting
            in real time.
          </p>
        </div>
        <button className="btn btn-primary" onClick={fireAll} disabled={!!busy || offline}>
          <Bug className="w-4 h-4" /> Run all attacks
        </button>
      </div>

      {offline && (
        <div className="card p-4 border border-amber-500/40 text-amber-200 bg-amber-500/5">
          The simulator is not active on this backend (live capture mode). The
          Attack Console only works when <code className="tag-mono">SIMULATE_TRAFFIC=true</code>.
        </div>
      )}

      {err && (
        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {err}
        </div>
      )}

      {/* Target card */}
      <div className="card p-5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center shrink-0">
            <Target className="w-5 h-5 text-cyan-400" />
          </div>
          <div className="flex-1">
            <div className="text-xs uppercase tracking-wider text-slate-400">Defended host</div>
            <div className="text-lg font-semibold text-slate-100">
              {info?.defended_host_name || '—'}{' '}
              <span className="text-cyan-300 tag-mono ml-2">{info?.defended_host_ip || '—'}</span>
            </div>
            <div className="text-xs text-slate-500 mt-1">
              All simulated benign traffic flows toward this IP, and every
              attack button below targets it. This is the host the NIDS is
              protecting on the local network.
            </div>
          </div>
          <div className="text-right text-xs text-slate-500 space-y-1">
            <div>Mode: <span className="text-slate-300">{info?.monitoring_mode}</span></div>
            <div>Attacks fired: <span className="text-slate-300">{info?.attacks_fired ?? 0}</span></div>
            {info?.last_attack_kind && (
              <div>Last: <span className="text-slate-300">{info.last_attack_kind}</span></div>
            )}
          </div>
        </div>
      </div>

      {/* Help banner */}
      <div className="card p-4 text-sm text-slate-300 flex items-start gap-3">
        <Info className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
        <div className="space-y-1.5">
          <div>
            <strong className="text-slate-100">How this works.</strong>{' '}
            The NIDS uses <em>real-time</em> packet inspection — it does not
            replay a stored PCAP. The simulator pushes synthetic frames
            through the same dispatcher that a live network interface would,
            so the alerts you generate here exercise the exact code path
            used by a real deployment.
          </div>
          <div>
            Click an attack to inject a single burst. The <em>Run all
            attacks</em> button cycles through every catalog entry with a
            half-second gap.
          </div>
        </div>
      </div>

      {/* Benign traffic toggle */}
      <div className="card p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center shrink-0">
            <Waves className="w-5 h-5 text-cyan-400" />
          </div>
          <div className="text-sm">
            <div className="font-semibold text-slate-100">Benign traffic baseline</div>
            <div className="text-slate-400 leading-relaxed mt-0.5">
              When enabled the simulator emits ~24–40 benign packets per second toward the
              defended host (HTTP, DNS, SSH). Useful for showing the system at rest, but
              off by default so the live packet graph stays flat until you fire an attack.
            </div>
          </div>
        </div>
        <button
          className={info?.benign_traffic ? 'btn btn-primary' : 'btn btn-ghost'}
          onClick={toggleBenign}
          disabled={offline}
        >
          {info?.benign_traffic ? 'Benign traffic: ON' : 'Benign traffic: OFF'}
        </button>
      </div>

      {/* Attack grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {(info?.available_attacks || []).map((a) => {
          const Icon = ICONS[a.kind] || Bug;
          return (
            <button
              key={a.kind}
              disabled={!!busy || offline}
              onClick={() => fire(a.kind)}
              className="card p-5 text-left transition-colors hover:border-cyan-500/40 disabled:opacity-50 disabled:cursor-not-allowed group"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/40 flex items-center justify-center shrink-0 group-hover:bg-amber-500/25 transition-colors">
                  <Icon className="w-5 h-5 text-amber-400" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-slate-100">{a.label}</h3>
                    {a.burst && <span className="chip chip-medium">burst</span>}
                  </div>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">{a.description}</p>
                  <div className="text-[11px] text-slate-500 mt-2">
                    kind: <code className="tag-mono">{a.kind}</code>
                  </div>
                </div>
              </div>
              <div className="mt-3 text-xs text-cyan-400 group-hover:text-cyan-300">
                {busy === a.kind ? 'Firing…' : 'Fire attack →'}
              </div>
            </button>
          );
        })}
      </div>

      {/* History */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Recent injections</h2>
          <Link to="/alerts" className="text-xs text-cyan-400 hover:text-cyan-300">
            View alerts →
          </Link>
        </div>
        {history.length === 0 ? (
          <div className="text-sm text-slate-500">
            No attacks fired yet from this session. Click any attack above to begin.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-slate-400">
              <tr className="text-left">
                <th className="px-2 py-2 font-medium">Time</th>
                <th className="px-2 py-2 font-medium">Attack</th>
                <th className="px-2 py-2 font-medium">From</th>
                <th className="px-2 py-2 font-medium">To</th>
                <th className="px-2 py-2 font-medium">Packets</th>
                <th className="px-2 py-2 font-medium">Alerts</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => {
                const gen = h.alerts_generated ?? 0;
                return (
                  <tr key={i} className="border-t border-navy-800">
                    <td className="px-2 py-2 text-slate-400 whitespace-nowrap">
                      {new Date(h.ts).toLocaleTimeString()}
                    </td>
                    <td className="px-2 py-2">
                      <span className="inline-flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
                        {h.kindLabel || h.kind}
                      </span>
                    </td>
                    <td className="px-2 py-2"><span className="tag-mono">{h.attacker}</span></td>
                    <td className="px-2 py-2"><span className="tag-mono">{h.target}</span></td>
                    <td className="px-2 py-2">{h.packet_count}</td>
                    <td className="px-2 py-2">
                      {gen > 0 ? (
                        <span className="chip chip-high">{gen} fired</span>
                      ) : (
                        <span className="chip chip-medium">no match</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
