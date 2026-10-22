import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import Heatmap from '../components/Heatmap';
import type { GridPoint } from '../components/Heatmap';
import Icon from '../components/Icons';
import { format, predictionVisible, range, sourcePreview } from '../lib/science';
import type { Model, Simulation, Source } from '../types';

const Surface = lazy(() => import('../components/Surface'));
const defaults: Source[] = [{ x: 0.36, y: 0.63, sigma: 0.085, amplitude: 1.2 }, { x: 0.67, y: 0.35, sigma: 0.105, amplitude: 0.9 }];

export default function PhysicsLab({ model }: { model: Model | null }) {
  const [sources, setSources] = useState<Source[]>(defaults);
  const [selected, setSelected] = useState(0);
  const [sigma, setSigma] = useState(0.085), [amplitude, setAmplitude] = useState(1.2);
  const [mode, setMode] = useState<'sources' | 'sample'>('sources'), [sample, setSample] = useState(0);
  const [result, setResult] = useState<Simulation | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  const [frame, setFrame] = useState(0), [playing, setPlaying] = useState(false), [surface, setSurface] = useState(false);
  const [point, setPoint] = useState<GridPoint | null>(null);
  const preview = useMemo(() => sourcePreview(sources, model?.physics.grid_size ?? 64), [sources, model]);
  const run = useCallback(async (initial = false, signal?: AbortSignal) => {
    setBusy(true); setError(null); setPlaying(false);
    try {
      const response = await api<Simulation>('/simulate', { ...(mode === 'sample' ? { sample_index: sample } : { sources }), frame_stride: 4 }, signal);
      setResult(response); setFrame(initial ? response.frames.length-1 : 0);
    } catch (err) { if (!(err instanceof DOMException && err.name === 'AbortError')) setError((err as Error).message); }
    finally { if (!signal?.aborted) setBusy(false); }
  }, [sources, mode, sample]);
  useEffect(() => { const controller = new AbortController(); void run(true, controller.signal); return () => controller.abort(); /* one initial computation, never training */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!playing || !result) return;
    const timer = window.setInterval(() => setFrame(current => { if (current >= result.frames.length-1) { setPlaying(false); return current; } return current+1; }), 90);
    return () => clearInterval(timer);
  }, [playing, result]);
  const invalidate = () => { setResult(null); setPlaying(false); setFrame(0); };
  const place = (x: number, y: number) => { if (mode !== 'sources' || sources.length >= 12 || busy) return; setSources([...sources, { x, y, sigma, amplitude }]); setSelected(sources.length); invalidate(); };
  const changeSource = (key: 'sigma' | 'amplitude', value: number) => {
    if (key === 'sigma') setSigma(value); else setAmplitude(value);
    setSources(current => current.map((source, index) => index === selected ? { ...source, [key]: value } : source)); invalidate();
  };
  const snapshot = result?.frames[frame];
  const final = result && snapshot && predictionVisible(snapshot.step, result.prediction_valid_at_step);
  const initial = result?.initial ?? (mode === 'sources' ? preview : null);
  const prediction = final ? result.prediction : null;
  const [low, high] = range([initial, snapshot?.field, prediction]);
  const [, errorHigh] = range([final ? result.absolute_error : null]);
  const physics = result?.physics ?? model?.physics;
  return <div className="page-enter">
    <div className="page-heading"><div><div className="eyebrow">SIMULATION WORKSPACE <span>/</span> 01</div><h1>Physics Lab</h1><p>Place heat. Watch it diffuse. Inspect the learned approximation.</p></div><span className="status-pill"><i className={busy ? 'dot amber pulse' : 'dot'}/>{busy ? 'Computing fields' : result ? 'Simulation ready' : 'Source preview'}</span></div>
    <div className="physics-meta"><span><Icon name="grid" size={14}/> {physics?.grid_size ?? 64} × {physics?.grid_size ?? 64} grid</span><span>α = {physics?.alpha ?? 0.1} L² / time</span><span>Zero Dirichlet boundary</span><span className="meta-right">Explicit Euler <b>→</b> Residual U-Net</span></div>
    {error && <div role="alert" className="error-message">{error}<button onClick={() => void run()}>Retry</button></div>}
    <div className="physics-workspace">
      <div className="field-workspace"><div className="heat-grid">
        <Heatmap title="Initial condition" subtitle={result ? 't = 0 · applied solver input' : 'Source preview · run simulation to apply'} badge="T₀" field={initial} low={low} high={high} point={point} onHover={setPoint} onPlace={mode === 'sources' ? place : undefined}/>
        <Heatmap title="Numerical reference" subtitle={`Explicit Euler · step ${snapshot?.step ?? '—'}`} badge="FDM" field={snapshot?.field ?? null} low={low} high={high} point={point} onHover={setPoint} empty="Run a simulation to compute the numerical field."/>
        <Heatmap title="Surrogate prediction" subtitle={prediction ? `Fixed final time · ${format(physics?.final_time, 6)}` : 'Available only at the trained final time'} badge="CNN" field={prediction} low={low} high={high} point={point} onHover={setPoint} empty={result?.model_error ?? `CNN output is revealed at step ${physics?.steps ?? 120}. Play or move to the final frame.`}/>
        <Heatmap title="Absolute prediction error" subtitle="|CNN − numerical reference| · final time only" badge="ΔT" field={final ? result.absolute_error : null} low={0} high={errorHigh} unit="|ΔT| · original units" point={point} onHover={setPoint} empty="Final-time comparison. No intermediate CNN predictions are implied."/>
      </div>
      <div className="playback panel"><div className="playback-top"><div className="button-group"><button className="icon-button play-button" aria-label={playing ? 'Pause simulation' : 'Play simulation'} disabled={!result || busy} onClick={() => { if (!playing && result && frame === result.frames.length-1) setFrame(0); setPlaying(!playing); }}><Icon name={playing ? 'pause' : 'play'}/></button><button className="icon-button" aria-label="Reset simulation to step zero" disabled={!result} onClick={() => { setPlaying(false); setFrame(0); }}><Icon name="reset"/></button><span>{playing ? 'PLAYING' : 'TIMELINE'}</span></div><code>t = {format(snapshot?.time, 6)} <span>/ {format(physics?.final_time, 6)}</span></code><span className="tiny-badge">STEP {snapshot?.step ?? '—'} / {physics?.steps ?? 120}</span></div>
        <input aria-label="Simulation timestep" type="range" min="0" max={Math.max(1, (result?.frames.length ?? 1)-1)} value={frame} disabled={!result} onChange={e => { setPlaying(false); setFrame(Number(e.target.value)); }}/><div className="timeline-labels"><span>Initial condition</span><span>Numerical evolution</span><span>CNN comparison <Icon name="check" size={12}/></span></div>
      </div>
      {surface && snapshot && <div className="panel surface-panel"><div className="panel-title"><h3>Numerical temperature surface</h3><span className="tiny-badge">STEP {snapshot.step}</span></div><Suspense fallback={<div className="loading-block">Loading surface renderer…</div>}><Surface field={snapshot.field} low={low} high={high}/></Suspense></div>}
      <div className="footnote"><Icon name="info" size={15}/><span>The reference is a discretized numerical solution. The CNN predicts one final time; intermediate animation frames come exclusively from the solver.</span></div></div>
      <aside className="control-rail"><fieldset disabled={busy} className="panel source-controls"><div className="panel-title"><h3>Experiment controls</h3><Icon name="heat"/></div>
        <div className="segmented"><button className={mode === 'sources' ? 'active' : ''} onClick={() => { setMode('sources'); invalidate(); }}>Place sources</button><button className={mode === 'sample' ? 'active' : ''} onClick={() => { setMode('sample'); invalidate(); }}>Held-out sample</button></div>
        {mode === 'sources' ? <>
          <div className="control-description"><Icon name="plus" size={14}/> Click the initial field to add a Gaussian source.</div>
          <div className="control-label"><label htmlFor="width">Gaussian width</label><code>{sigma.toFixed(3)} L</code></div><input id="width" type="range" min="0.01" max="0.25" step="0.005" value={sigma} onChange={e => changeSource('sigma', Number(e.target.value))}/><div className="slider-ticks"><span>Narrow</span><span>Broad</span></div>
          <div className="control-label"><label htmlFor="intensity">Source intensity</label><code>{amplitude.toFixed(2)}</code></div><input id="intensity" type="range" min="0.1" max="3" step="0.05" value={amplitude} onChange={e => changeSource('amplitude', Number(e.target.value))}/><div className="slider-ticks"><span>0.10</span><span>3.00</span></div>
          <div className="section-label">ACTIVE SOURCES <span>{sources.length} / 12</span></div><div className="source-list">{sources.map((source, index) => <div key={index} className={`source-row ${index === selected ? 'selected' : ''}`}><button onClick={() => { setSelected(index); setSigma(source.sigma); setAmplitude(source.amplitude); }}><span className="source-number">{String(index+1).padStart(2, '0')}</span><span><b>Gaussian source</b><code>x {source.x.toFixed(2)} · y {source.y.toFixed(2)}</code></span></button><button className="icon-button" aria-label={`Remove source ${index+1}`} onClick={() => { const next = sources.filter((_, i) => i !== index); setSources(next); setSelected(0); if (next[0]) { setSigma(next[0].sigma); setAmplitude(next[0].amplitude); } invalidate(); }}><Icon name="close" size={13}/></button></div>)}{sources.length === 0 && <p className="muted small">No sources. The zero-input solution is zero.</p>}</div>
          <button className="text-button" onClick={() => { setSources([]); invalidate(); }}>Clear all sources</button>
        </> : <><p className="control-description">Inspect a real cached test field from the checkpoint dataset.</p><label className="control-label" htmlFor="sample">Test sample index</label><input id="sample" className="number-input" type="number" min="0" max={(model?.test_samples ?? 300)-1} value={sample} onChange={e => { setSample(Math.max(0, Math.min((model?.test_samples ?? 300)-1, Number(e.target.value)))); invalidate(); }}/><p className="small muted">{model?.test_samples ?? '—'} held-out fields · training labels remain separate</p></>}
        <button className="primary-button full-width" disabled={busy} onClick={() => void run()}><Icon name={busy ? 'reset' : 'play'} size={15}/>{busy ? 'Computing…' : 'Run simulation'}<kbd>↵</kbd></button>
      </fieldset>
      <section className="panel numerical-card"><div className="panel-title"><h3>Numerical configuration</h3></div><dl><div><dt>Time step Δt</dt><dd>{format(physics?.effective_dt, 8)}</dd></div><div><dt>CFL coefficient r</dt><dd>{format(physics?.alpha_dt_over_dx2)}</dd></div><div><dt>Trained final time</dt><dd>{format(physics?.final_time, 6)}</dd></div><div><dt>Inference device</dt><dd className="uppercase">{model?.device ?? '—'}</dd></div></dl><div className="stability"><Icon name="check" size={14}/> Stable 2D CFL · r ≤ 0.25</div><button className={`secondary-button full-width ${surface ? 'active' : ''}`} disabled={!result} onClick={() => setSurface(!surface)}><Icon name="cube" size={15}/>{surface ? 'Hide 3D surface' : 'View 3D surface'}</button></section>
      <section className="panel error-card"><div className="panel-title"><h3>This field · final-time error</h3></div>{final && result.metrics ? <dl><div><dt>RMSE</dt><dd>{format(result.metrics.rmse, 6)}</dd></div><div><dt>Relative L2</dt><dd>{format(result.metrics.relative_l2*100, 3)}%</dd></div><div><dt>MAE</dt><dd>{format(result.metrics.mae, 6)}</dd></div></dl> : <p className="small muted">Metrics appear at the trained final timestep.</p>}<p className="small muted">Custom source configurations can be outside the training distribution.</p></section>
      </aside>
    </div>
  </div>;
}
