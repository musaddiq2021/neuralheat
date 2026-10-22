import { useEffect, useRef, useState } from 'react';
import type { Matrix } from '../types';
import { color, colorGradient, format } from '../lib/science';

export interface GridPoint { x: number; y: number }
interface Props { field: Matrix | null; title: string; subtitle?: string; badge?: string; low: number; high: number; unit?: string; point?: GridPoint | null; onHover?: (p: GridPoint | null) => void; onPlace?: (x: number, y: number) => void; empty?: string; compact?: boolean }
export default function Heatmap({ field, title, subtitle, badge, low, high, unit = 'T · original units', point, onHover, onPlace, empty, compact }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [localPoint, setLocalPoint] = useState<GridPoint | null>(null);
  const activePoint = point === undefined ? localPoint : point;
  const size = field?.length ?? 64;
  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    if (!context || !field) return;
    const image = context.createImageData(size, size);
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const [r, g, b] = color(field[y][x], low, high), index = ((size-1-y)*size+x)*4;
      image.data.set([r, g, b, 255], index);
    }
    context.putImageData(image, 0, 0);
  }, [field, size, low, high]);
  const value = activePoint && field ? field[activePoint.y]?.[activePoint.x] : null;
  return <section className={`heat-panel ${compact ? 'compact' : ''}`}>
    <div className="panel-title"><div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>{badge && <span className="tiny-badge">{badge}</span>}</div>
    {field ? <div className="heat-body">
      <div className="heat-axis"><span>{compact ? size-1 : '1.0'}</span><span>{compact ? (size-1)/2 : '0.5'}</span><span>{compact ? '0' : '0.0'}</span><b>{compact ? 'row index' : 'y / L'}</b></div>
      <div className={`heat-canvas-wrap ${onPlace ? 'placeable' : ''}`}
        onMouseMove={event => { const rect = event.currentTarget.getBoundingClientRect(); const next = { x: Math.max(0, Math.min(size-1, Math.round((event.clientX-rect.left)/rect.width*(size-1)))), y: Math.max(0, Math.min(size-1, Math.round((1-(event.clientY-rect.top)/rect.height)*(size-1)))) }; setLocalPoint(next); onHover?.(next); }}
        onMouseLeave={() => { setLocalPoint(null); onHover?.(null); }}
        onClick={event => { const rect = event.currentTarget.getBoundingClientRect(); onPlace?.(Math.max(0, Math.min(1, (event.clientX-rect.left)/rect.width)), Math.max(0, Math.min(1, 1-(event.clientY-rect.top)/rect.height))); }}
        role={onPlace ? 'button' : undefined} tabIndex={onPlace ? 0 : undefined}
        aria-label={onPlace ? 'Temperature field. Click to place a source, or press Enter for a central source.' : title}
        onKeyDown={e => { if (onPlace && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onPlace(0.5, 0.5); } }}>
        <canvas ref={canvas} width={size} height={size} aria-label={title}/>
        <div className="plot-grid"/>
        {activePoint && <><i className="crosshair vertical" style={{ left: `${activePoint.x/(size-1)*100}%` }}/><i className="crosshair horizontal" style={{ top: `${(1-activePoint.y/(size-1))*100}%` }}/></>}
      </div>
      <div className="color-scale"><div style={{ background: colorGradient }}/><span>{format(high)}</span><span>{format((high+low)/2)}</span><span>{format(low)}</span></div>
      <div className="x-axis"><span>{compact ? '0' : '0.0'}</span><span>{compact ? (size-1)/2 : '0.5'} <b>{compact ? 'column index' : 'x / L'}</b></span><span>{compact ? size-1 : '1.0'}</span></div>
    </div> : <div className="empty-heat"><span className="empty-grid"/><p>{empty ?? 'No field available'}</p></div>}
    <div className="heat-footer"><span>{unit}</span><code>{field ? activePoint ? `(${activePoint.x}, ${activePoint.y})  ${format(value, 6)}` : `${size} × ${size} nodes` : '—'}</code></div>
  </section>;
}
