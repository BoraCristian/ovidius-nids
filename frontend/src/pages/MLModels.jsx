import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { Brain, Play, CheckCircle2, Flame, Info } from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { apiGet, apiPost } from '../api/client.js';

const DEFAULT_NAMES = {
  random_forest:    'baseline-rf',
  isolation_forest: 'baseline-iforest',
};

const ALGO_HELP = {
  random_forest:
    'Supervised classifier — learns "malicious vs benign" from labelled flow ' +
    'features. Great when you have both attack and normal traffic samples. ' +
    'Outputs both a label AND a probability score.',
  isolation_forest:
    'Unsupervised anomaly detector — trained only on normal traffic. Flags ' +
    'anything that looks unlike what it has seen before. Use this when you ' +
    'don\'t have labelled attacks but want "outlier" coverage.',
};

export default function MLModels() {
  const [models, setModels] = useState([]);
  const [status, setStatus] = useState({ active: false, feature_names: [] });
  const [busy, setBusy] = useState(false);
  const [algorithm, setAlgorithm] = useState('random_forest');
  const [name, setName] = useState(DEFAULT_NAMES.random_forest);
  const [err, setErr] = useState('');

  // When the user flips between algorithms, default the name accordingly
  // (but only if they haven't customised it).
  function changeAlgorithm(next) {
    setAlgorithm(next);
    const allDefaults = new Set(Object.values(DEFAULT_NAMES));
    if (allDefaults.has(name)) setName(DEFAULT_NAMES[next] || name);
  }

  async function load() {
    setModels(await apiGet('/api/ml/models'));
    setStatus(await apiGet('/api/ml/status'));
  }
  useEffect(() => { load(); }, []);

  async function train() {
    setErr(''); setBusy(true);
    try {
      await apiPost('/api/ml/train', { name, algorithm, dataset: 'synthetic', activate: true });
      await load();
    } catch (e) {
      setErr(e.message || 'Training failed');
    } finally {
      setBusy(false);
    }
  }

  async function activate(id) {
    await apiPost(`/api/ml/activate/${id}`, {});
    await load();
  }

  const active = models.find(m => m.is_active);
  const isIForest = active?.algorithm === 'isolation_forest';

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Brain className="w-6 h-6 text-fuchsia-400" /> ML Models
        </h1>
        <p className="text-slate-400 text-sm">
          Train and deploy machine-learning classifiers. ML-flagged packets that aren't matched by a signature
          become stand-alone alerts; packets hit by both a signature and the model become <em>hybrid</em>.
        </p>
      </div>

      <div className="card p-4 text-sm text-slate-300 flex items-start gap-3">
        <Info className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
        <div className="space-y-1.5">
          <div>
            <strong className="text-slate-100">How this page works.</strong>{' '}
            Pick an algorithm, give the model a name, click <em>Train + activate</em>. Training
            runs on a synthetic dataset of benign + attack flow features (6 features per packet:
            src/dst ports, length, protocol, TCP flag mask, inter-arrival time). Once a model is
            activated, the dispatcher feeds every captured packet through it in real time.
          </div>
          <div>
            <strong className="text-slate-100">Metrics.</strong>{' '}
            <span className="tag-mono">Accuracy</span> = overall % correct ·{' '}
            <span className="tag-mono">Precision</span> = of flagged packets, how many were
            really malicious ·{' '}
            <span className="tag-mono">Recall</span> = of all malicious packets, how many we
            caught ·{' '}
            <span className="tag-mono">F1</span> = harmonic mean of precision and recall.
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-5 lg:col-span-1">
          <h2 className="font-semibold mb-3">Train a new model</h2>
          {err && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 mb-3">{err}</div>}
          <div className="space-y-3">
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1">Name</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1">Algorithm</label>
              <select className="input" value={algorithm} onChange={e => changeAlgorithm(e.target.value)}>
                <option value="random_forest">Random Forest (supervised)</option>
                <option value="isolation_forest">Isolation Forest (anomaly)</option>
              </select>
              <div className="text-xs text-slate-500 mt-2 leading-relaxed">
                {ALGO_HELP[algorithm]}
              </div>
            </div>
            <button className="btn btn-primary w-full justify-center" disabled={busy} onClick={train}>
              <Play className="w-4 h-4" /> {busy ? 'Training…' : 'Train + activate'}
            </button>
            <div className="text-xs text-slate-500">
              Dataset: synthetic (mixed benign + attack flow features).
              Re-training with the same name auto-appends <code className="tag-mono">-2</code>,{' '}
              <code className="tag-mono">-3</code>… so you never overwrite an existing model.
            </div>
          </div>
        </div>

        <div className="card p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Active model</h2>
            <span className={`chip ${status.active ? 'chip-low' : 'chip-medium'}`}>
              {status.active ? 'loaded' : 'not loaded'}
            </span>
          </div>
          {active ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="tag-mono">{active.name}</span>
                <span>·</span>
                <span>{active.algorithm}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <Kpi label="Accuracy"  value={active.accuracy?.toFixed(3)}  hint="Overall % correct on the held-out test set." />
                <Kpi label="Precision" value={active.precision?.toFixed(3)} hint="Of packets flagged malicious, % that really were." />
                <Kpi label="Recall"    value={active.recall?.toFixed(3)}    hint="Of all malicious packets, % we caught." />
                <Kpi label="F1"        value={active.f1?.toFixed(3)}        hint="Harmonic mean of precision and recall." />
              </div>
              <div>
                <div className="text-xs uppercase text-slate-400 mb-1">Feature importance</div>
                {isIForest ? (
                  <div className="text-xs text-slate-500 leading-relaxed border border-navy-800 rounded-lg px-3 py-3">
                    Isolation Forest is an unsupervised tree ensemble — it doesn't expose per-feature
                    importances the way Random Forest does. The model still uses all 6 features
                    (src/dst port, length, protocol, flag mask, inter-arrival) to score anomalies.
                  </div>
                ) : (
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={Object.entries(active.feature_importance || {}).map(([k, v]) => ({ name: k, value: v }))}>
                        <CartesianGrid stroke="#1A2D4F" strokeDasharray="3 3" />
                        <XAxis dataKey="name" stroke="#64748B" fontSize={11} />
                        <YAxis stroke="#64748B" fontSize={11} />
                        <Tooltip
                          contentStyle={{ background: '#0A1220', border: '1px solid #1A2D4F', borderRadius: 8, color: '#E2E8F0' }}
                          itemStyle={{ color: '#E2E8F0' }}
                          labelStyle={{ color: '#94A3B8' }}
                        />
                        <Bar dataKey="value" fill="#D946EF" radius={[4,4,0,0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-400">No active model. Train one on the left.</div>
          )}
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="p-4 border-b border-navy-800 flex items-center justify-between">
          <h2 className="font-semibold">Model registry</h2>
          <span className="text-xs text-slate-500">{models.length} total</span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-navy-850 text-slate-400">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Algorithm</th>
              <th className="px-4 py-3 font-medium">Accuracy</th>
              <th className="px-4 py-3 font-medium">F1</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Active</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {models.map(m => (
              <tr key={m.id} className="border-t border-navy-800">
                <td className="px-4 py-2">{m.name}</td>
                <td className="px-4 py-2">{m.algorithm}</td>
                <td className="px-4 py-2">{m.accuracy?.toFixed(3) ?? '—'}</td>
                <td className="px-4 py-2">{m.f1?.toFixed(3) ?? '—'}</td>
                <td className="px-4 py-2 text-slate-400">{format(new Date(m.created_at), 'MMM d HH:mm')}</td>
                <td className="px-4 py-2">
                  {m.is_active
                    ? <span className="chip chip-low"><CheckCircle2 className="w-3 h-3" /> active</span>
                    : <span className="chip chip-medium"><Flame className="w-3 h-3" /> idle</span>}
                </td>
                <td className="px-4 py-2">
                  {!m.is_active && (
                    <button className="btn btn-ghost !py-1 !px-2" onClick={() => activate(m.id)}>
                      <Play className="w-3.5 h-3.5" /> Activate
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!models.length && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-500">No models trained yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Kpi({ label, value, hint }) {
  return (
    <div className="border border-navy-800 rounded-lg px-3 py-2" title={hint}>
      <div className="text-xs uppercase text-slate-400">{label}</div>
      <div className="text-lg font-semibold">{value ?? '—'}</div>
      {hint && <div className="text-[10px] text-slate-500 leading-snug mt-1">{hint}</div>}
    </div>
  );
}
