import Sidebar from './Sidebar.jsx';
import TopBar from './TopBar.jsx';
import { useLiveAlerts } from '../hooks/useLiveAlerts.js';
import { useLiveTraffic } from '../hooks/useLiveTraffic.js';
import { createContext, useContext, useMemo } from 'react';

/**
 * Live state shared across the whole authenticated session.
 *
 * Both the alert WebSocket subscription and the rolling 60-second packet-rate
 * buffer live here, in the Layout, instead of inside the page that consumes
 * them. That way they survive route changes: navigating away from the
 * Dashboard and back doesn't tear down the buffer, so the chart picks up
 * where it left off instead of resetting to zero.
 */
const LiveContext = createContext({
  alerts: [], connected: false, traffic: [], trafficConnected: false,
});
export const useLive = () => useContext(LiveContext);

export default function Layout({ children }) {
  const liveAlerts  = useLiveAlerts(150);
  const liveTraffic = useLiveTraffic(60);

  const value = useMemo(() => ({
    alerts:           liveAlerts.alerts,
    connected:        liveAlerts.connected,
    traffic:          liveTraffic.series,
    trafficConnected: liveTraffic.connected,
  }), [liveAlerts.alerts, liveAlerts.connected, liveTraffic.series, liveTraffic.connected]);

  return (
    <LiveContext.Provider value={value}>
      <div className="h-full flex">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar live={value.connected} />
          <main className="flex-1 overflow-auto p-6">
            {children}
          </main>
        </div>
      </div>
    </LiveContext.Provider>
  );
}
