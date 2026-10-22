import { useEffect, useRef, useState } from 'react';
import { openWebSocket } from '../api/client.js';

/**
 * Live traffic aggregator.
 *
 * Maintains a rolling window of `maxSeconds` one-second buckets, advanced by a
 * 1 Hz ticker. Incoming WebSocket packets increment the "current" bucket; the
 * ticker then snapshots it into the series and starts a fresh one.
 *
 * Returns `{ series, connected }` where `series` is an array of
 * `{ t: Date, count, bytes }` ready to be plotted by Recharts.
 */
export function useLiveTraffic(maxSeconds = 60) {
  const [series, setSeries] = useState(() => emptySeries(maxSeconds));
  const [connected, setConnected] = useState(false);

  const currentRef = useRef({ count: 0, bytes: 0 });
  const wsRef = useRef(null);

  // Tick: shift the window one bucket left every second.
  useEffect(() => {
    const id = setInterval(() => {
      const bucket = currentRef.current;
      const now = new Date();
      setSeries(prev => [
        ...prev.slice(1),
        { t: now, count: bucket.count, bytes: bucket.bytes },
      ]);
      currentRef.current = { count: 0, bytes: 0 };
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // WebSocket: accumulate into the current bucket.
  useEffect(() => {
    let cancelled = false;
    let retries = 0;

    function connect() {
      const ws = openWebSocket('/ws/traffic');
      wsRef.current = ws;
      ws.onopen  = () => { setConnected(true); retries = 0; };
      ws.onerror = () => ws.close();
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          // Exponential-ish backoff capped at 3s.
          setTimeout(connect, Math.min(3000, 500 * ++retries));
        }
      };
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg?.type === 'traffic_batch' && Array.isArray(msg.events)) {
            const bucket = currentRef.current;
            for (const e of msg.events) {
              bucket.count += 1;
              bucket.bytes += Number(e.length || 0);
            }
          }
        } catch { /* ignore non-JSON frames */ }
      };
    }

    connect();
    return () => {
      cancelled = true;
      try { wsRef.current?.close(); } catch { /* noop */ }
    };
  }, []);

  return { series, connected };
}

function emptySeries(len) {
  const now = Date.now();
  return Array.from({ length: len }, (_, i) => ({
    t: new Date(now - (len - i) * 1000),
    count: 0,
    bytes: 0,
  }));
}
