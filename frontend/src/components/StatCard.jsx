import clsx from 'clsx';

export default function StatCard({ label, value, hint, icon: Icon, tone = 'cyan' }) {
  const tones = {
    cyan:   'text-cyan-300 bg-cyan-500/10 border-cyan-500/30',
    amber:  'text-amber-300 bg-amber-500/10 border-amber-500/30',
    red:    'text-red-300 bg-red-500/10 border-red-500/30',
    slate:  'text-slate-300 bg-slate-500/10 border-slate-500/30',
  };
  return (
    <div className="card card-hover p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400">{label}</div>
          <div className="text-2xl font-semibold mt-1">{value}</div>
          {hint ? <div className="text-xs text-slate-500 mt-1">{hint}</div> : null}
        </div>
        {Icon && (
          <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center border', tones[tone])}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>
    </div>
  );
}
