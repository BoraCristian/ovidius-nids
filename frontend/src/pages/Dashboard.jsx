import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { ShieldAlert, Activity, Waves, Gauge, Target } from 'lucide-react';
import { apiGet } from '../api/client.js';
import StatCard from '../components/StatCard.jsx';
import SeverityBadge from '../components/SeverityBadge.jsx';
import MethodBadge from '../components/MethodBadge.jsx';
import { useLive } from '../components/Layout.jsx';
import { format } from 'date-fns';

const SEV_COLORS = { low: '#38BDF8', medium: '#FACC15', high: '#FB923C', critical: '#EF4444' };
const METHOD_COLORS = { signature: '#22D3EE', ml: '#D946EF', hybrid: '#10B981' };

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  // Both live alerts and the rolling packet-rate buffer come from the Layout
  // context so they survive navigation away from this page.
  const { alerts: liveAlerts, traffic } = useLive();

  useEffect(() => {
    let alive = true;
    async function refresh() {
      try {
        const [s, h] = await Promise.all([
          apiGet('/api/dashboard/summary'),
          apiGet('/api/health'),
        ]);
        if (!alive) return;
        setSummary(s);
        setHealth(h);
      } catch { /* ignore */ }
    }
    refresh();
    const id = setInterval(refresh, 5000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const severityData = Object.entries(summary?.severity_distribution || {}).map(([name, value]) => ({ name, value }));
  const methodData   = Object.entries(summary?.method_distribution   || {}).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Operations Dashboard</h1>
          <p className="text-slate-400 text-sm">Live overview of detections from the signature and ML engines.</p>
        </div>
        {health?.defended_host_ip && (
          <Link to="/attack"
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-sm hover:bg-cyan-500/15 transition-colors"
            title="Click to open the Attack Console"
          >
            <Target className="w-4 h-4 text-cyan-400" />
            <div className="leading-tight">
              <div className="text-[10px] uppercase tracking-wider text-slate-400">
                Monitoring host ({health.monitoring_mode})
              </div>
              <div className="font-mono text-cyan-300 text-sm">
                {health.defended_host_name} <span className="text-slate-400">·</span> {health.defended_host_ip}
              </div>
            </div>
          </Link>
        )}
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Alerts (24h)"        value={summary?.alerts_total ?? '—'} icon={ShieldAlert} tone="red" />
        <StatCard label="Open alerts"         value={summary?.alerts_open  ?? '—'} hint="Status = new" icon={Gauge} tone="amber" />
        <StatCard label="Packets processed"   value={(summary?.packets_seen ?? 0).toLocaleString()} icon={Waves} tone="cyan" />
        <StatCard label="Packets / second"    value={(summary?.pps ?? 0).toFixed(1)} icon={Activity} tone="cyan" />
      </div>

      {/* Live flow + live alerts */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="card p-4 xl:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Live packet rate (last 60s)</h2>
            <span className="chip chip-low">WebSocket</span>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              {/*
                isAnimationActive={false} stops Recharts from animating between
                the old and new series on every window shift — that animation is
                what caused the curve to "wiggle" each second.  With animation
                off and a linear interpolation, the line just steps to the left
                one bucket at a time and renders a stable shape.
              */}
              <AreaChart data={traffic}>
                <defs>
                  <linearGradient id="flowGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"  stopColor="#22D3EE" stopOpacity={0.6}/>
                    <stop offset="100%" stopColor="#22D3EE" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1A2D4F" strokeDasharray="3 3" />
                <XAxis
                  dataKey="t"
                  tickFormatter={(t) => format(new Date(t), 'HH:mm:ss')}
                  stroke="#64748B" fontSize={11}
                  minTickGap={40}
                />
                <YAxis stroke="#64748B" fontSize={11} allowDecimals={false} />
                <Tooltip
                  labelFormatter={(t) => format(new Date(t), 'HH:mm:ss')}
                  contentStyle={{ background: '#0A1220', border: '1px solid #1A2D4F', borderRadius: 8, color: '#E2E8F0' }}
                  itemStyle={{ color: '#E2E8F0' }}
                  labelStyle={{ color: '#94A3B8' }}
                />
                <Area
                  type="linear"
                  dataKey="count"
                  stroke="#22D3EE"
                  strokeWidth={2}
                  fill="url(#flowGradient)"
                  isAnimationActive={false}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Severity (24h)</h2>
            <Link to="/alerts" className="text-xs text-cyan-400 hover:text-cyan-300">View all →</Link>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={severityData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70}>
                  {severityData.map((e, i) => (
                    <Cell key={i} fill={SEV_COLORS[e.name] || '#64748B'} />
                  ))}
                </Pie>
                <Legend verticalAlign="bottom" height={24} formatter={(v) => <span className="text-slate-300 text-xs">{v}</span>} />
                <Tooltip
                  contentStyle={{ background: '#0A1220', border: '1px solid #1A2D4F', borderRadius: 8, color: '#E2E8F0' }}
                  itemStyle={{ color: '#E2E8F0' }}
                  labelStyle={{ color: '#94A3B8' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Timeline + Top talkers */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="card p-4 xl:col-span-2">
          <h2 className="font-semibold mb-3">Alert timeline — last 6h (10-min buckets)</h2>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={summary?.alerts_timeline || []}>
                <CartesianGrid stroke="#1A2D4F" strokeDasharray="3 3" />
                <XAxis
                  dataKey="ts"
                  tickFormatter={(t) => format(new Date(t), 'HH:mm')}
                  stroke="#64748B" fontSize={11}
                />
                <YAxis stroke="#64748B" fontSize={11} />
                <Tooltip
                  labelFormatter={(t) => format(new Date(t), 'HH:mm')}
                  contentStyle={{ background: '#0A1220', border: '1px solid #1A2D4F', borderRadius: 8, color: '#E2E8F0' }}
                  itemStyle={{ color: '#E2E8F0' }}
                  labelStyle={{ color: '#94A3B8' }}
                />
                <Bar dataKey="count" fill="#22D3EE" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-4">
          <h2 className="font-semibold mb-3">Detection method mix</h2>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={methodData} dataKey="value" nameKey="name" outerRadius={80} label>
                  {methodData.map((e, i) => (
                    <Cell key={i} fill={METHOD_COLORS[e.name] || '#64748B'} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0A1220', border: '1px solid #1A2D4F', borderRadius: 8, color: '#E2E8F0' }}
                  itemStyle={{ color: '#E2E8F0' }}
                  labelStyle={{ color: '#94A3B8' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Top talkers + Live feed */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="card p-4">
          <h2 className="font-semibold mb-3">Top source IPs</h2>
          <ul className="space-y-2">
            {(summary?.top_src_ips || []).map((it) => (
              <li key={it.key} className="flex items-center justify-between">
                <span className="tag-mono">{it.key}</span>
                <span className="text-slate-300 text-sm">{it.count}</span>
              </li>
            ))}
            {!summary?.top_src_ips?.length && <li className="text-sm text-slate-500">No data yet.</li>}
          </ul>
        </div>

        <div className="card p-4">
          <h2 className="font-semibold mb-3">Top destination ports</h2>
          <ul className="space-y-2">
            {(summary?.top_dst_ports || []).map((it) => (
              <li key={it.key} className="flex items-center justify-between">
                <span className="tag-mono">:{it.key}</span>
                <span className="text-slate-300 text-sm">{it.count}</span>
              </li>
            ))}
            {!summary?.top_dst_ports?.length && <li className="text-sm text-slate-500">No data yet.</li>}
          </ul>
        </div>

        <div className="card p-4 xl:col-span-1">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Live alert feed</h2>
            <Link to="/alerts" className="text-xs text-cyan-400 hover:text-cyan-300">Alerts →</Link>
          </div>
          <ul className="space-y-2 max-h-[420px] overflow-auto pr-2">
            {liveAlerts.map((a) => (
              <li key={a.id} className="border border-navy-800 rounded-lg p-3 hover:border-cyan-500/30 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <SeverityBadge value={a.severity} />
                    <MethodBadge value={a.detection_method} />
                  </div>
                  <time className="text-xs text-slate-500">
                    {a.ts && format(new Date(a.ts), 'HH:mm:ss')}
                  </time>
                </div>
                <div className="mt-1 text-sm text-slate-200 truncate">{a.message}</div>
                <div className="mt-1 text-xs text-slate-400">
                  <span className="tag-mono">{a.src_ip}:{a.src_port}</span>
                  <span className="mx-1">→</span>
                  <span className="tag-mono">{a.dst_ip}:{a.dst_port}</span>
                </div>
              </li>
            ))}
            {!liveAlerts.length && (
              <li className="text-sm text-slate-500">Waiting for first detection…</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
