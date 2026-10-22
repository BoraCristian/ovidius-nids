import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { ScrollText, Plus, Trash2, Pencil, Save, X } from 'lucide-react';
import { apiDelete, apiGet, apiPatch, apiPost } from '../api/client.js';
import SeverityBadge from '../components/SeverityBadge.jsx';
import ConfirmDialog from '../components/ConfirmDialog.jsx';

const emptyRule = {
  name: '',
  description: '',
  category: 'generic',
  severity: 'medium',
  enabled: true,
  action: 'alert',
  match: { protocol: 'tcp' },
};

export default function Rules() {
  const [rules, setRules] = useState([]);
  const [editing, setEditing] = useState(null);   // rule object or 'new'
  const [matchText, setMatchText] = useState('{}');
  const [err, setErr] = useState('');
  const [toDelete, setToDelete] = useState(null); // rule awaiting deletion confirmation

  async function load() {
    setRules(await apiGet('/api/rules'));
  }
  useEffect(() => { load(); }, []);

  function startEdit(rule) {
    setErr('');
    setEditing(rule);
    setMatchText(JSON.stringify(rule.match || {}, null, 2));
  }
  function startNew() {
    setErr('');
    setEditing({ ...emptyRule });
    setMatchText(JSON.stringify(emptyRule.match, null, 2));
  }
  function cancel() {
    setEditing(null);
    setErr('');
  }

  async function save() {
    let match;
    try { match = JSON.parse(matchText); }
    catch (e) { setErr(`Invalid JSON in match: ${e.message}`); return; }
    const payload = { ...editing, match };
    try {
      if (editing.id) {
        await apiPatch(`/api/rules/${editing.id}`, payload);
      } else {
        await apiPost('/api/rules', payload);
      }
      await load();
      setEditing(null);
    } catch (e) {
      setErr(e.message || 'Save failed');
    }
  }

  function askRemove(rule) {
    setToDelete(rule);
  }

  async function confirmRemove() {
    const rule = toDelete;
    setToDelete(null);
    if (!rule) return;
    try {
      await apiDelete(`/api/rules/${rule.id}`);
      await load();
    } catch (e) {
      setErr(e.message || 'Failed to delete rule');
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <ScrollText className="w-6 h-6 text-cyan-400" /> Signature rules
          </h1>
          <p className="text-slate-400 text-sm">
            Rules are evaluated against every packet. Disabled rules are excluded from the engine.
          </p>
        </div>
        <button className="btn btn-primary" onClick={startNew}><Plus className="w-4 h-4" /> New rule</button>
      </div>

      {editing && (
        <div className="card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{editing.id ? `Edit rule #${editing.id}` : 'Create a new rule'}</h2>
            <div className="flex items-center gap-2">
              <button className="btn btn-ghost" onClick={cancel}><X className="w-4 h-4" /> Cancel</button>
              <button className="btn btn-primary" onClick={save}><Save className="w-4 h-4" /> Save</button>
            </div>
          </div>
          {err && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">{err}</div>}

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <input className="input md:col-span-2" placeholder="Name" value={editing.name}
              onChange={e => setEditing({ ...editing, name: e.target.value })} />
            <select className="input" value={editing.severity}
              onChange={e => setEditing({ ...editing, severity: e.target.value })}>
              {['low', 'medium', 'high', 'critical'].map(s => <option key={s} value={s}>severity: {s}</option>)}
            </select>
            <input className="input" placeholder="Category" value={editing.category}
              onChange={e => setEditing({ ...editing, category: e.target.value })} />
            <textarea className="input md:col-span-4 min-h-[60px]" placeholder="Description"
              value={editing.description || ''}
              onChange={e => setEditing({ ...editing, description: e.target.value })} />
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={editing.enabled}
                onChange={e => setEditing({ ...editing, enabled: e.target.checked })} />
              Enabled
            </label>
            <select className="input" value={editing.action}
              onChange={e => setEditing({ ...editing, action: e.target.value })}>
              <option value="alert">action: alert</option>
              <option value="log">action: log</option>
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs uppercase tracking-wider text-slate-400">Match specification (JSON)</span>
              <span className="text-xs text-slate-500">
                keys: protocol, src_ip, dst_ip, src_port, dst_port, flags, content, regex, min_length, threshold
              </span>
            </div>
            <textarea
              className="input font-mono text-xs min-h-[180px]"
              value={matchText}
              onChange={e => setMatchText(e.target.value)}
              spellCheck={false}
            />
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-navy-850 text-slate-400">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">#</th>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Severity</th>
              <th className="px-4 py-3 font-medium">Category</th>
              <th className="px-4 py-3 font-medium">Match</th>
              <th className="px-4 py-3 font-medium">Enabled</th>
              <th className="px-4 py-3 font-medium">Updated</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {rules.map(r => (
              <tr key={r.id} className="border-t border-navy-800 hover:bg-navy-850/50">
                <td className="px-4 py-2 text-slate-500">{r.id}</td>
                <td className="px-4 py-2 font-medium text-slate-100">{r.name}</td>
                <td className="px-4 py-2"><SeverityBadge value={r.severity} /></td>
                <td className="px-4 py-2">{r.category}</td>
                <td className="px-4 py-2 text-xs font-mono text-slate-400 truncate max-w-md">
                  {JSON.stringify(r.match)}
                </td>
                <td className="px-4 py-2">
                  <span className={`chip ${r.enabled ? 'chip-low' : 'chip-medium'}`}>
                    {r.enabled ? 'enabled' : 'disabled'}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-400 whitespace-nowrap">
                  {r.updated_at && format(new Date(r.updated_at), 'MMM d HH:mm')}
                </td>
                <td className="px-4 py-2 whitespace-nowrap space-x-2">
                  <button className="btn btn-ghost !py-1 !px-2" onClick={() => startEdit(r)}>
                    <Pencil className="w-3.5 h-3.5" /> Edit
                  </button>
                  <button className="btn btn-danger !py-1 !px-2" onClick={() => askRemove(r)}>
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                </td>
              </tr>
            ))}
            {!rules.length && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-500">No rules. Click <strong>New rule</strong> to create one.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={!!toDelete}
        title="Delete rule?"
        message={
          toDelete ? (
            <>
              This will permanently remove <span className="tag-mono">{toDelete.name}</span> from
              the signature engine. Future packets won't be matched against it. This can't be undone.
            </>
          ) : null
        }
        confirmText="Delete rule"
        cancelText="Keep it"
        destructive
        onConfirm={confirmRemove}
        onCancel={() => setToDelete(null)}
      />
    </div>
  );
}
