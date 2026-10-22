import { useEffect, useRef, useState } from 'react';
import { openWebSocket } from '../api/client.js';

/** Subscribe to /ws/alerts and keep a rolling buffer of recent detections. */
export function useLiveAlerts(limit = 100) {
  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    let retry = 0;
    let cancelled = false;

    function connect() {
      const ws = openWebSocket('/ws/alerts');
      wsRef.current = ws;
      ws.onopen  = () => { setConnected(true); retry = 0; };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(connect, Math.min(3000, 500 * ++retry));
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg && msg.type === 'alert') {
            setAlerts(prev => [msg, ...prev].slice(0, limit));
          }
        } catch { /* ignore */ }
      };
    }
    connect();
    return () => { cancelled = true; try { wsRef.current && wsRef.current.close(); } catch {} };
  }, [limit]);

  return { alerts, connected };
}
