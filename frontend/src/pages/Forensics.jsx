import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { Search, Download } from 'lucide-react';
import { apiDownload, apiGet } from '../api/client.js';

export default function Forensics() {
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState('');
  useEffect(() => { apiGet('/api/forensics/pcaps').then(setRows); }, []);

  async function download(pcap) {
    setErr('');
    try {
      await apiDownload(
        `/api/forensics/alert/${pcap.alert_id}/download`,
        pcap.filename || `alert-${pcap.alert_id}.jsonl`,
      );
    } catch (e) {
      setErr(`Could not download capture: ${e.message || 'unknown error'}`);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Search className="w-6 h-6 text-cyan-400" /> Forensics
        </h1>
        <p className="text-slate-400 text-sm">
          Every alert triggers a packet snapshot. Open an alert to replay the events around it.
        </p>
      </div>

      {err && (
        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {err}
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-navy-850 text-slate-400">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">#</th>
              <th className="px-4 py-3 font-medium">File</th>
              <th className="px-4 py-3 font-medium">Alert</th>
              <th className="px-4 py-3 font-medium">Packets</th>
              <th className="px-4 py-3 font-medium">Size</th>
              <th className="px-4 py-3 font-medium">Captured</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(p => (
              <tr key={p.id} className="border-t border-navy-800 hover:bg-navy-850/50">
                <td className="px-4 py-2 text-slate-500">{p.id}</td>
                <td className="px-4 py-2 font-mono text-slate-300 truncate max-w-xs">{p.filename}</td>
                <td className="px-4 py-2">
                  {p.alert_id ? (
                    <Link to={`/alerts/${p.alert_id}`} className="text-cyan-400 hover:text-cyan-300">#{p.alert_id}</Link>
                  ) : '—'}
                </td>
                <td className="px-4 py-2">{p.packet_count}</td>
                <td className="px-4 py-2 text-slate-400">{(p.size_bytes / 1024).toFixed(1)} KB</td>
                <td className="px-4 py-2 text-slate-400">
                  {format(new Date(p.created_at), 'MMM d HH:mm:ss')}
                </td>
                <td className="px-4 py-2">
                  {p.alert_id && (
                    <button
                      className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300"
                      onClick={() => download(p)}
                    >
                      <Download className="w-3.5 h-3.5" /> Download
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-500">No captures yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
