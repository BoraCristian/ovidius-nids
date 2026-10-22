import clsx from 'clsx';
import { AlertCircle, AlertTriangle, Flame, Info } from 'lucide-react';

const config = {
  low:      { cls: 'chip-low',      Icon: Info },
  medium:   { cls: 'chip-medium',   Icon: AlertCircle },
  high:     { cls: 'chip-high',     Icon: AlertTriangle },
  critical: { cls: 'chip-critical', Icon: Flame },
};

export default function SeverityBadge({ value = 'medium' }) {
  const { cls, Icon } = config[value] || config.medium;
  return (
    <span className={clsx('chip', cls)}>
      <Icon className="w-3 h-3" />
      {value}
    </span>
  );
}
