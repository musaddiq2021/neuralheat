import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { LossChart } from '../components/Charts';
import Icon from '../components/Icons';
import { format } from '../lib/science';
import type { Experiment, Hardware, LossPoint, RunDetail } from '../types';

const terminal = new Set(['completed', 'failed', 'cancelled', 'interrupted']);
export default function TrainingRoom({ run, hardware, onRefresh }: { run: RunDetail | null; hardware: Hardware | null; onRefresh: () => void }) {
  const [experiments, setExperiments] = useState<Experiment[]>([]), [selected, setSelected] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null), [connected, setConnected] = useState(false);
  const consoleEnd = useRef<HTMLDivElement>(null), consoleBox = useRef<HTMLDivElement>(null), stick = useRef(true);
  const active = experiments.find(item => !terminal.has(item.status));
  const experiment = experiments.find(item => item.id === selected) ?? active;
  const identifier = experiment?.id;
  const history = experiment?.history ?? run?.training?.history ?? [];
  useEffect(() => { let mounted = true; api<Experiment[]>('/experiments').then(items => { if (mounted) setExperiments(items); }).catch(err => { if (mounted) setError(err.message); }); return () => { mounted = false; }; }, []);
  useEffect(() => {
    if (identifier || !run) return;
    const controller = new AbortController();
    api<{ lines: string[] }>(`/runs/${run.id}/logs?kind=training`, undefined, controller.signal).then(response => setLogs(response.lines)).catch(err => { if (err.name !== 'AbortError') setLogs([]); });
    return () => controller.abort();
  }, [identifier, run]);
  useEffect(() => {
    if (!identifier) return;
    setLogs([]); setConnected(false); stick.current = true;
    const source = new EventSource(`/api/experiments/${identifier}/events`);
    let lastId = 0;
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener('log', (event: MessageEvent) => { const id = Number(event.lastEventId); if (id <= lastId) return; lastId = id; setLogs(current => [...current.slice(-2999), JSON.parse(event.data).line]); });
    source.addEventListener('epoch', (event: MessageEvent) => {
      const point: LossPoint = JSON.parse(event.data);
      setExperiments(items => items.map(item => item.id !== identifier ? item : { ...item, epoch: point.epoch, history: [...item.history.filter(p => p.epoch !== point.epoch), point].sort((a, b) => a.epoch-b.epoch) }));
    });
    source.addEventListener('state', (event: MessageEvent) => {
      const update: Experiment = JSON.parse(event.data);
      setExperiments(items => items.some(item => item.id === update.id) ? items.map(item => item.id === update.id ? update : item) : [update, ...items]);
    });
    source.addEventListener('end', () => { source.close(); setConnected(false); onRefresh(); });
    return () => source.close();
  }, [identifier, onRefresh]);
  useEffect(() => { if (stick.current && consoleBox.current) consoleBox.current.scrollTop = consoleBox.current.scrollHeight; }, [logs]);
  const start = async (preset: 'smoke' | 'full') => {
    setBusy(true); setError(null);
    try { const item = await api<Experiment>('/experiments', { preset }); setExperiments(items => [item, ...items]); setSelected(item.id); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  const cancel = async () => {
    if (!active) return;
    setBusy(true); setError(null);
    try { const item = await api<Experiment>(`/experiments/${active.id}/cancel`, {}); setExperiments(items => items.map(old => old.id === item.id ? item : old)); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  const gpu = hardware?.gpu;
  return <div className="page-enter"><div className="page-heading"><div><div className="eyebrow">EXPERIMENT OPERATIONS <span>/</span> 03</div><h1>Training Control Room</h1><p>Launch approved experiments. Follow every epoch. Keep an auditable record.</p></div><span className="status-pill"><i className={active ? 'dot amber pulse' : 'dot'}/>{active ? 'Experiment running' : 'Worker idle'}</span></div>
    {error && <div role="alert" className="error-message">{error}</div>}
    <div className="training-launch panel"><div><Icon name="terminal" size={24}/><div><h3>Experiment runner</h3><p>Each launch writes a new isolated run. Opening Studio never starts training.</p></div></div><div className="launch-buttons"><button className="secondary-button" disabled={busy || !!active} onClick={() => void start('smoke')}><Icon name="play" size={14}/>Start smoke <span>3 epochs</span></button><button className="primary-button" disabled={busy || !!active} onClick={() => void start('full')}><Icon name="play" size={14}/>Start full <span>80 max</span></button><button className="danger-button" disabled={busy || !active} onClick={() => void cancel()}><Icon name="close" size={15}/>{active?.status === 'cancelling' ? 'Cancelling…' : 'Cancel'}</button></div></div>
    <div className="metric-strip training-metrics"><div><span>{experiment ? 'Live experiment status' : 'Saved run status'}</span><b className="capitalize">{experiment?.status ?? run?.studio?.status ?? run?.execution?.status ?? 'No run'}</b></div><div><span>Epoch</span><b>{experiment ? `${experiment.epoch} / ${experiment.epoch_limit}` : `${run?.training?.epochs_executed ?? '—'} recorded`}</b></div><div><span>Latest validation MSE</span><b>{format(history.at(-1)?.validation)}</b></div><div><span>Compute backend</span><b>{hardware?.cuda_available ? `CUDA ${hardware.cuda_version}` : 'CPU'}</b></div></div>
    <div className="training-grid"><section className="panel loss-panel"><div className="panel-title"><div><h3>Optimization history</h3><p>{experiment ? 'Live logged epoch losses · normalized temperatures' : 'Saved training history · no new training performed'}</p></div><span className="tiny-badge">MSE / ADAM</span></div><LossChart history={history}/></section><section className="panel hardware-panel"><div className="panel-title"><h3>Live compute telemetry</h3><Icon name="cpu"/></div><div className="gpu-name">{gpu?.name ?? (hardware?.cuda_available ? 'CUDA device' : 'CPU runtime')}</div><dl><div><dt>GPU utilization</dt><dd>{format(gpu?.utilization_percent, 0)}{gpu?.utilization_percent == null ? '' : '%'}</dd></div><div><dt>Device memory</dt><dd>{format(gpu?.memory_used_mib, 0)} / {format(gpu?.memory_total_mib, 0)} MiB</dd></div><div><dt>Temperature</dt><dd>{format(gpu?.temperature_c, 0)}{gpu?.temperature_c == null ? '' : ' °C'}</dd></div><div><dt>Inference device</dt><dd>{hardware?.inference_device ?? '—'}</dd></div></dl><div className="memory-track"><span style={{ width: gpu?.memory_used_mib != null && gpu.memory_total_mib ? `${gpu.memory_used_mib/gpu.memory_total_mib*100}%` : '0%' }}/></div><p className="small muted">{hardware?.telemetry_error ?? 'nvidia-smi device-wide telemetry · includes other processes · refreshed every 5 s'}</p></section></div>
    <section className="panel console-panel"><div className="panel-title"><div className="console-caption"><Icon name="terminal"/><h3>Experiment console</h3><span className={connected ? 'console-live' : 'muted'}>{connected ? '● STREAMING' : experiment ? 'SAVED LOG' : 'SAVED TRAINING LOG'}</span></div><code>{experiment?.id ?? 'reference / training.log'}</code></div><div ref={consoleBox} className="console" role="log" aria-label="Experiment output" aria-live="polite" onScroll={() => { const box = consoleBox.current; if (box) stick.current = box.scrollHeight-box.scrollTop-box.clientHeight < 45; }}>{logs.length ? logs.map((line, index) => <div key={index} className={/error|failed|traceback/i.test(line) ? 'console-error' : /epoch \d+/.test(line) ? 'console-epoch' : ''}><span className="line-number">{String(index+1).padStart(3, '0')}</span><span>{line || ' '}</span></div>) : <div className="console-placeholder"><span className="prompt">$</span> {experiment ? 'Waiting for process output…' : 'No active experiment. Start a preset to stream its output.'}</div>}<div ref={consoleEnd}/></div><div className="console-footer"><span><i className={connected ? 'dot' : 'dot neutral'}/>{connected ? 'Server-sent events connected' : 'No live stream'}</span><span>{logs.length} lines · approved presets only · no shell access</span></div></section>
    <section className="panel experiment-history"><div className="panel-title"><h3>Experiment history</h3><button className="text-button" onClick={() => { setSelected(null); }}>Show selected saved run</button></div><div className="table-scroll"><table><thead><tr><th>Run</th><th>Preset</th><th>Started</th><th>Epoch</th><th>Status</th></tr></thead><tbody>{experiments.map(item => <tr key={item.id} onClick={() => setSelected(item.id)} tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') setSelected(item.id); }}><td><code>{item.id}</code></td><td>{item.preset}</td><td>{new Date(item.started_at).toLocaleString()}</td><td>{item.epoch}</td><td><span className={`run-status ${item.status}`}>{item.status}</span></td></tr>)}{!experiments.length && <tr><td colSpan={5} className="empty-table">No dashboard experiments yet. Existing CLI runs remain available in the saved-run selector.</td></tr>}</tbody></table></div></section>
  </div>;
}
