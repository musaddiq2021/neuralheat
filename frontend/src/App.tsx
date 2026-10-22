import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { api } from './api';
import Icon from './components/Icons';
import type { Hardware, Model, RunDetail, SavedRun } from './types';

const PhysicsLab = lazy(() => import('./pages/PhysicsLab'));
const NetworkExplorer = lazy(() => import('./pages/NetworkExplorer'));
const TrainingRoom = lazy(() => import('./pages/TrainingRoom'));
const LatencyLab = lazy(() => import('./pages/LatencyLab'));
const Overview = lazy(() => import('./pages/Overview'));
const navigation = [{ id: 'overview', title: 'Overview', icon: 'grid', section: 'WORKSPACE' }, { id: 'physics', title: 'Physics Lab', icon: 'heat', number: '01' }, { id: 'network', title: 'Network Explorer', icon: 'network', number: '02' }, { id: 'training', title: 'Training Room', icon: 'terminal', number: '03' }, { id: 'latency', title: 'Latency Lab', icon: 'chart', number: '04' }];

export default function App() {
  const [page, setPage] = useState(() => { const p = location.hash.slice(1); return navigation.some(n => n.id === p) ? p : 'physics'; });
  const [model, setModel] = useState<Model | null>(null), [hardware, setHardware] = useState<Hardware | null>(null);
  const [runs, setRuns] = useState<SavedRun[]>([]), [runId, setRunId] = useState('primary'), [run, setRun] = useState<RunDetail | null>(null);
  const [online, setOnline] = useState(false), [error, setError] = useState<string | null>(null), [menu, setMenu] = useState(false), [runLoading, setRunLoading] = useState(false);
  const [desktop, setDesktop] = useState(false);
  const refresh = useCallback(() => { api<SavedRun[]>('/runs').then(setRuns).catch(err => setError(err.message)); }, []);
  useEffect(() => {
    const controller = new AbortController();
    api<Model>('/model', undefined, controller.signal).then(setModel).catch(err => { if (err.name !== 'AbortError') setError(`Model API: ${err.message}`); });
    refresh();
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => {
    let mounted = true;
    const poll = () => {
      api<{ status: string; mode?: string }>('/health').then(value => { if (mounted) { setOnline(true); setDesktop(value.mode === 'desktop'); } }).catch(() => { if (mounted) setOnline(false); });
      api<Hardware>('/hardware').then(value => { if (mounted) setHardware(value); }).catch(() => { /* unavailable hardware is not a synthetic measurement */ });
    };
    poll(); const timer = window.setInterval(poll, 5000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);
  useEffect(() => {
    const controller = new AbortController(); setRunLoading(true); setRun(null);
    api<RunDetail>(`/runs/${runId}`, undefined, controller.signal).then(value => { setRun(value); setError(null); }).catch(err => { if (err.name !== 'AbortError') setError(err.message); }).finally(() => { if (!controller.signal.aborted) setRunLoading(false); });
    return () => controller.abort();
  }, [runId]);
  useEffect(() => { const handler = () => { const value = location.hash.slice(1); if (navigation.some(n => n.id === value)) setPage(value); }; window.addEventListener('hashchange', handler); return () => window.removeEventListener('hashchange', handler); }, []);
  const navigate = (id: string) => { setPage(id); location.hash = id; setMenu(false); };
  const selected = navigation.find(item => item.id === page)!;
  return <div className="app-shell selection:bg-slate-600 selection:text-white"><aside className={`sidebar ${menu ? 'open' : ''}`}><a className="brand" href="#overview" onClick={() => navigate('overview')}><span className="brand-symbol"><i/><i/><i/></span><span>NEURALHEAT<small>STUDIO <b>{desktop ? 'DESKTOP' : 'LOCAL'}</b></small></span></a><div className="project-card"><span className="project-monogram">NH</span><div><strong>Heat surrogate</strong><span>Scientific ML workspace</span></div><Icon name="chevron" size={13}/></div><nav aria-label="Main navigation"><div className="nav-label">WORKSPACE</div>{navigation.map(item => <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} aria-current={page === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><Icon name={item.icon} size={18}/><span>{item.title}</span>{item.number && <small>{item.number}</small>}</button>)}</nav><div className="sidebar-bottom"><div className="runtime-card"><div><i className={online ? 'dot' : 'dot amber'}/><span>{online ? 'Backend connected' : 'Backend unavailable'}</span></div><code>{desktop ? 'Managed local engine' : '127.0.0.1:8000'}</code><div className="runtime-device"><Icon name="cpu" size={14}/>{model?.available ? `${model.device.toUpperCase()} inference ready` : 'Model unavailable'}</div></div><div className="sidebar-footer"><span className="avatar">N</span><div><b>Local workspace</b><span>Data stays on this machine</span></div></div></div></aside>
    {menu && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMenu(false)}/>}
    <div className="main-shell"><header className="topbar"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMenu(!menu)}><Icon name="menu"/></button><div className="breadcrumb"><span>Workspace</span><Icon name="chevron" size={12}/><b>{selected.title}</b></div><div className="topbar-right"><label className="run-selector"><Icon name="folder" size={14}/><select aria-label="Saved experiment" value={runId} onChange={e => setRunId(e.target.value)}>{runs.length ? runs.map(item => <option key={item.id} value={item.id}>{item.label}{item.has_benchmark ? ' · measured' : ''}</option>) : <option value="primary">Reference run</option>}</select></label><span className="topbar-divider"/><span className="local-indicator"><i className={online ? 'dot' : 'dot amber'}/>{online ? desktop ? 'DESKTOP READY' : 'SYSTEM ONLINE' : 'CONNECTING'}</span></div></header>
      <main id="main-content">{(!online || error) && <div className="connection-banner" role="status"><Icon name="info" size={16}/><span>{error ?? (desktop ? 'The local engine is unavailable. Restart Studio or inspect its application logs.' : 'Connecting to the local API. Check that the FastAPI backend is running on port 8000.')}</span><button className="text-button" onClick={() => location.reload()}>Reconnect</button></div>}
      <Suspense fallback={<div className="loading-block"><span className="spinner"/>Loading workspace…</div>}>{page === 'physics' && <PhysicsLab model={model}/>} {page === 'network' && <NetworkExplorer model={model}/>} {page === 'training' && <TrainingRoom run={run} hardware={hardware} onRefresh={refresh}/>} {page === 'latency' && (runLoading ? <div className="loading-block">Reading saved report…</div> : <LatencyLab run={run}/>)} {page === 'overview' && <Overview model={model} run={run} hardware={hardware} navigate={navigate}/>}</Suspense>
      </main><footer className="app-footer"><span>NEURALHEAT STUDIO <b>v1.0</b></span><span>Physics-informed inspection · evidence-based performance</span><code>float32 / 64²</code></footer>
    </div>
  </div>;
}
