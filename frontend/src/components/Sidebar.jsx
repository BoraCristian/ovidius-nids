import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Siren, ScrollText, Brain, Search, Settings, ShieldCheck, Zap,
} from 'lucide-react';
import clsx from 'clsx';

const links = [
  { to: '/',            label: 'Dashboard',      icon: LayoutDashboard },
  { to: '/alerts',      label: 'Alerts',         icon: Siren },
  { to: '/rules',       label: 'Rules',          icon: ScrollText },
  { to: '/ml',          label: 'ML Models',      icon: Brain },
  { to: '/forensics',   label: 'Forensics',      icon: Search },
  { to: '/attack',      label: 'Attack Console', icon: Zap },
  { to: '/settings',    label: 'Settings',       icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 h-full bg-navy-900/60 border-r border-navy-800 flex flex-col">
      <div className="px-5 py-5 flex items-center gap-3 border-b border-navy-800">
        <div className="w-9 h-9 rounded-lg bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center">
          <ShieldCheck className="w-5 h-5 text-cyan-400" />
        </div>
        <div>
          <div className="font-semibold tracking-tight text-slate-50">Ovidius NIDS</div>
          <div className="text-[11px] uppercase tracking-wider text-slate-400">SIEM console</div>
        </div>
      </div>
      <nav className="p-3 flex-1 space-y-1">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-300 hover:bg-navy-800 hover:text-slate-100 border border-transparent',
              )
            }
          >
            <Icon className="w-4 h-4" /> {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-navy-800 text-xs text-slate-500">
        Bachelor's Thesis · UOC · FMI
      </div>
    </aside>
  );
}
