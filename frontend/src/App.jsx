import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout.jsx';
import { useAuth } from './store/auth.jsx';
import Login from './pages/Login.jsx';

// Pages are code-split and loaded on first visit; the Suspense boundary in
// RequireAuth keeps the sidebar/top bar interactive while a page chunk loads.
const Dashboard     = lazy(() => import('./pages/Dashboard.jsx'));
const Alerts        = lazy(() => import('./pages/Alerts.jsx'));
const AlertDetail   = lazy(() => import('./pages/AlertDetail.jsx'));
const Rules         = lazy(() => import('./pages/Rules.jsx'));
const MLModels      = lazy(() => import('./pages/MLModels.jsx'));
const Forensics     = lazy(() => import('./pages/Forensics.jsx'));
const Settings      = lazy(() => import('./pages/Settings.jsx'));
const AttackConsole = lazy(() => import('./pages/AttackConsole.jsx'));

function RequireAuth({ children }) {
  const { user, booting } = useAuth();
  if (booting) {
    return (
      <div className="h-full w-full flex items-center justify-center text-slate-400">
        <span className="animate-pulse">Loading console…</span>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return (
    <Layout>
      <Suspense fallback={<div className="text-slate-400 animate-pulse">Loading page…</div>}>
        {children}
      </Suspense>
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/"           element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/alerts"     element={<RequireAuth><Alerts /></RequireAuth>} />
      <Route path="/alerts/:id" element={<RequireAuth><AlertDetail /></RequireAuth>} />
      <Route path="/rules"      element={<RequireAuth><Rules /></RequireAuth>} />
      <Route path="/ml"         element={<RequireAuth><MLModels /></RequireAuth>} />
      <Route path="/forensics"  element={<RequireAuth><Forensics /></RequireAuth>} />
      <Route path="/attack"     element={<RequireAuth><AttackConsole /></RequireAuth>} />
      <Route path="/settings"   element={<RequireAuth><Settings /></RequireAuth>} />
      <Route path="*"           element={<Navigate to="/" replace />} />
    </Routes>
  );
}
