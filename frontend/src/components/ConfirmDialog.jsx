import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, X } from 'lucide-react';

/**
 * Themed confirmation modal.
 *
 * Replaces the browser's default `window.confirm()` so destructive actions
 * stay inside the SIEM's visual language (navy panel, cyan accents, rounded
 * corners) instead of breaking the immersion with an OS-native pop-up.
 *
 * Props:
 *   open        - boolean, controls visibility
 *   title       - string
 *   message     - ReactNode / string (what the user is agreeing to)
 *   confirmText - string, defaults to "Confirm"
 *   cancelText  - string, defaults to "Cancel"
 *   destructive - boolean, red primary button if true (default false)
 *   onConfirm   - () => void
 *   onCancel    - () => void
 */
export default function ConfirmDialog({
  open,
  title = 'Are you sure?',
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  destructive = false,
  onConfirm,
  onCancel,
}) {
  // Close on Escape, confirm on Enter — feels more native.
  useEffect(() => {
    if (!open) return;
    function handleKey(e) {
      if (e.key === 'Escape') onCancel?.();
      if (e.key === 'Enter')  onConfirm?.();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onConfirm, onCancel]);

  if (!open) return null;

  const confirmClass = destructive
    ? 'btn btn-danger'
    : 'btn btn-primary';

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel?.(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-navy-950/70 backdrop-blur-sm" />

      {/* Panel */}
      <div className="card relative w-full max-w-md p-6 shadow-xl">
        <button
          type="button"
          aria-label="Close"
          onClick={onCancel}
          className="absolute top-3 right-3 text-slate-400 hover:text-slate-200"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
            destructive
              ? 'bg-red-500/15 border border-red-500/40'
              : 'bg-cyan-500/15 border border-cyan-500/40'
          }`}>
            <AlertTriangle className={`w-5 h-5 ${destructive ? 'text-red-400' : 'text-cyan-400'}`} />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-slate-100">{title}</h3>
            {message && (
              <div className="text-sm text-slate-300 mt-1">
                {message}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 mt-6">
          <button className="btn btn-ghost" onClick={onCancel}>{cancelText}</button>
          <button className={confirmClass} onClick={onConfirm} autoFocus>{confirmText}</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
