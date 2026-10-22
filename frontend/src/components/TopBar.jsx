import { LogOut, Activity, Wifi, WifiOff } from 'lucide-react';
import { useAuth } from '../store/auth.jsx';

export default function TopBar({ live }) {
  const { user, logout } = useAuth();
  return (
    <header className="h-14 border-b border-navy-800 bg-navy-900/40 backdrop-blur-sm px-5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-2 text-sm text-slate-300">
          <Activity className="w-4 h-4 text-cyan-400" /> Live detection engine
        </span>
        <span className={`chip ${live ? 'chip-low' : 'chip-high'}`}>
          {live ? <><Wifi className="w-3 h-3" />connected</> : <><WifiOff className="w-3 h-3" />disconnected</>}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-400">
          Signed in as <span className="text-slate-200 font-medium">{user?.username || '—'}</span>
          <span className="text-slate-500"> · {user?.role}</span>
        </span>
        <button onClick={logout} className="btn btn-ghost" title="Sign out">
          <LogOut className="w-4 h-4" /> Sign out
        </button>
      </div>
    </header>
  );
}
