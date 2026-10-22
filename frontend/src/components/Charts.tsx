import { useId, useState } from 'react';
import type { Latency, LossPoint } from '../types';
import { format, methodLabel } from '../lib/science';

export function LossChart({ history }: { history: LossPoint[] }) {
  const id = useId();
  const [hover, setHover] = useState<LossPoint | null>(null);
  const points = history.filter(p => p.train > 0 && p.validation > 0);
  if (!points.length) return <div className="chart-empty">Loss curves appear when actual epochs are recorded.</div>;
  const logs = points.flatMap(p => [Math.log10(p.train), Math.log10(p.validation)]);
  const low = Math.floor(Math.min(...logs)), high = Math.max(low+1, Math.ceil(Math.max(...logs)));
  const x = (epoch: number) => 64+(epoch-1)/Math.max(1, points[points.length-1].epoch-1)*660;
  const y = (value: number) => 226-(Math.log10(value)-low)/(high-low)*200;
  return <div className="line-chart"><div className="chart-legend"><span><i style={{ background: '#90b9d6' }}/>Training</span><span><i style={{ background: '#e7ae72' }}/>Validation</span><code>MSE · log scale</code></div>
    <svg viewBox="0 0 760 268" role="img" aria-label="Recorded training and validation loss by epoch">
      <defs><clipPath id={id}><rect x="62" y="20" width="666" height="210"/></clipPath></defs>
      {Array.from({ length: high-low+1 }, (_, i) => low+i).map(t => <g key={t}><line x1="64" x2="724" y1={y(10**t)} y2={y(10**t)} stroke="#30353a" strokeDasharray="3 5"/><text x="52" y={y(10**t)+4} textAnchor="end">1e{t}</text></g>)}
      {[0, 0.25, 0.5, 0.75, 1].map(f => { const epoch = 1+Math.round(f*(points[points.length-1].epoch-1)); return <text key={f} x={x(epoch)} y="250" textAnchor="middle">{epoch}</text>; })}
      <g clipPath={`url(#${id})`}>{(['train', 'validation'] as const).map(key => <polyline key={key} fill="none" stroke={key === 'train' ? '#90b9d6' : '#e7ae72'} strokeWidth="2" points={points.map(p => `${x(p.epoch)},${y(p[key])}`).join(' ')}/>)}</g>
      {points.map(p => <rect key={p.epoch} x={x(p.epoch)-Math.max(4, 330/points.length)} y="20" width={Math.max(8, 660/points.length)} height="210" fill="transparent" onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)}><title>{`Epoch ${p.epoch} · train ${p.train} · validation ${p.validation}`}</title></rect>)}
      <text x="394" y="266" textAnchor="middle">Epoch</text>
    </svg>
    <div className="chart-readout">{hover ? `Epoch ${hover.epoch} · Training ${format(hover.train)} · Validation ${format(hover.validation)}` : `${points.length} recorded epochs · normalized temperatures · linear segments`}</div>
  </div>;
}

export const methodColors: Record<string, string> = { numpy_cpu_solver: '#a6afb9', torch_cpu_forward: '#7197b2', torch_cpu_end_to_end: '#9dbbd0', torch_cuda_forward: '#d0a776', torch_cuda_end_to_end: '#edb980' };
export function LatencyBars({ rows, metric = 'median_ms' }: { rows: Latency[]; metric?: 'median_ms' | 'p95_ms' | 'throughput_samples_per_second' }) {
  const maximum = Math.max(1e-9, ...rows.map(r => r[metric]));
  return <div className="latency-bars">{rows.map(row => <div key={row.method} className="latency-bar-row"><div><span>{methodLabel(row.method)}</span><code>{format(row[metric], 3)} <small>{metric === 'throughput_samples_per_second' ? 'samples/s' : 'ms'}</small></code></div><div className="bar-track"><span style={{ width: `${Math.max(0.4, row[metric]/maximum*100)}%`, background: methodColors[row.method] ?? '#a6afb9' }}/></div></div>)}</div>;
}
