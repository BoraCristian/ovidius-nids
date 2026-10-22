import clsx from 'clsx';
import { Fingerprint, Brain, CircuitBoard } from 'lucide-react';

export default function MethodBadge({ value }) {
  const map = {
    signature: { label: 'signature', cls: 'bg-cyan-500/10 border-cyan-500/40 text-cyan-300', Icon: Fingerprint },
    ml:        { label: 'ML',        cls: 'bg-fuchsia-500/10 border-fuchsia-500/40 text-fuchsia-300', Icon: Brain },
    hybrid:    { label: 'hybrid',    cls: 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300', Icon: CircuitBoard },
  };
  const { label, cls, Icon } = map[value] || map.signature;
  return (
    <span className={clsx('chip', cls)}>
      <Icon className="w-3 h-3" />
      {label}
    </span>
  );
}
