import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { format } from 'date-fns';
import { ArrowLeft, Download } from 'lucide-react';
import { apiDownload, apiGet } from '../api/client.js';
import SeverityBadge from '../components/SeverityBadge.jsx';
import MethodBadge from '../components/MethodBadge.jsx';

export default function AlertDetail() {
  const { id } = useParams();
  const [alert, setAlert] = useState(null);
  const [packets, setPackets] = useState([]);
  const [dlErr, setDlErr] = useState('');

  async function downloadCapture() {
    setDlErr('');
    try {
      await apiDownload(
        `/api/forensics/alert/${id}/download`,
        `alert-${id}.jsonl`,
      );
    } catch (e) {
      setDlErr(`Could not download capture: ${e.message || 'unknown error'}`);
    }
  }

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const a = await apiGet(`/api/alerts/${id}`);
        if (!alive) return;
        setAlert(a);
        const pkts = await apiGet(`/api/forensics/alert/${id}/packets`);
        if (alive) setPackets(pkts);
      } catch { /* ignore */ }
    }
    load();
    return () => { alive = false; };
  }, [id]);

  if (!alert) {
    return <div className="text-slate-400">Loading alert…</div>;
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <Link to="/alerts" className="btn btn-ghost">
          <ArrowLeft className="w-4 h-4" /> Back to alerts
        </Link>
        <button className="btn btn-primary" onClick={downloadCapture}>
          <Download className="w-4 h-4" /> Download packet log
        </button>
      </div>

      {dlErr && (
        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {dlErr}
        </div>
      )}

      <div className="card p-5">
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <SeverityBadge value={alert.severity} />
          <MethodBadge value={alert.detection_method} />
          <span className="chip chip-low">{alert.category}</span>
          <span className="text-xs text-slate-500">
            {alert.ts && format(new Date(alert.ts), 'yyyy-MM-dd HH:mm:ss')}
          </span>
        </div>
        <h1 className="text-xl font-semibold">{alert.rule_name || 'Untitled detection'}</h1>
        <p className="text-slate-300 mt-1">{alert.message}</p>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <InfoRow k="Source" v={<span className="tag-mono">{alert.src_ip}:{alert.src_port}</span>} />
          <InfoRow k="Destination" v={<span className="tag-mono">{alert.dst_ip}:{alert.dst_port}</span>} />
          <InfoRow k="Protocol" v={alert.protocol} />
          {alert.ml_score != null && (
            <InfoRow k="ML score" v={alert.ml_score.toFixed ? alert.ml_score.toFixed(3) : alert.ml_score} />
          )}
          <InfoRow k="Status" v={alert.status} />
          <InfoRow k="PCAP" v={alert.pcap_path ? <span className="tag-mono">{alert.pcap_path}</span> : '—'} />
        </div>

        {alert.raw_payload && (
          <div className="mt-4">
            <div className="text-xs uppercase text-slate-400 mb-1">Raw payload preview</div>
            <pre className="bg-navy-950 border border-navy-800 rounded-lg p-3 text-xs font-mono overflow-auto max-h-60">
              {alert.raw_payload}
            </pre>
          </div>
        )}
      </div>

      <div className="card p-5">
        <h2 className="font-semibold mb-3">Packet timeline (last {packets.length})</h2>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-400">
              <tr className="text-left">
                <th className="px-2 py-2 font-medium">Time</th>
                <th className="px-2 py-2 font-medium">Proto</th>
                <th className="px-2 py-2 font-medium">Source</th>
                <th className="px-2 py-2 font-medium">Destination</th>
                <th className="px-2 py-2 font-medium">Flags</th>
                <th className="px-2 py-2 font-medium">Len</th>
                <th className="px-2 py-2 font-medium">Payload</th>
              </tr>
            </thead>
            <tbody>
              {packets.map((p, i) => (
                <tr key={i} className="border-t border-navy-800 font-mono">
                  <td className="px-2 py-1 text-slate-400">{p.ts && format(new Date(p.ts), 'HH:mm:ss')}</td>
                  <td className="px-2 py-1">{p.protocol}</td>
                  <td className="px-2 py-1">{p.src_ip}:{p.src_port}</td>
                  <td className="px-2 py-1">{p.dst_ip}:{p.dst_port}</td>
                  <td className="px-2 py-1 text-cyan-300">{p.flags}</td>
                  <td className="px-2 py-1">{p.length}</td>
                  <td className="px-2 py-1 truncate max-w-xs text-slate-400">{p.payload_preview}</td>
                </tr>
              ))}
              {!packets.length && (
                <tr><td colSpan={7} className="px-2 py-6 text-center text-slate-500">No packets captured for this alert.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-4 border border-navy-800 rounded-lg px-3 py-2">
      <span className="text-xs uppercase tracking-wider text-slate-400">{k}</span>
      <span className="text-slate-200">{v ?? '—'}</span>
    </div>
  );
}
