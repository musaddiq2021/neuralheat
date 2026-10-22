import type { Matrix, Source } from '../types';

export function format(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return '—';
  if (value !== 0 && (Math.abs(value) < 0.001 || Math.abs(value) >= 1e5)) return value.toExponential(2);
  return value.toLocaleString('en-US', { maximumFractionDigits: digits });
}

// Inferno anchors, linearly interpolated. Every color encodes an actual scalar.
const inferno = [[0, 0, 4], [31, 12, 72], [85, 15, 109], [136, 34, 106], [186, 54, 85], [227, 89, 51], [249, 140, 10], [249, 201, 50], [252, 255, 164]];
export function color(value: number, low: number, high: number): [number, number, number] {
  const t = high > low ? Math.min(1, Math.max(0, (value-low)/(high-low))) : 0;
  const scaled = t*(inferno.length-1);
  const a = Math.min(inferno.length-2, Math.floor(scaled)), f = scaled-a;
  return [0, 1, 2].map(i => Math.round(inferno[a][i]*(1-f) + inferno[a+1][i]*f)) as [number, number, number];
}
export const colorGradient = `linear-gradient(to top, ${inferno.map(c => `rgb(${c.join(',')})`).join(',')})`;

export function range(fields: (Matrix | null | undefined)[]): [number, number] {
  let low = Infinity, high = -Infinity;
  for (const field of fields) for (const row of field ?? []) for (const value of row) { low = Math.min(low, value); high = Math.max(high, value); }
  return Number.isFinite(low) ? [low, high > low ? high : low + 1] : [0, 1];
}

export function sourcePreview(sources: Source[], n = 64): Matrix {
  return Array.from({ length: n }, (_, y) => Array.from({ length: n }, (_, x) => {
    if (x === 0 || y === 0 || x === n-1 || y === n-1) return 0;
    return sources.reduce((sum, s) => sum + s.amplitude*Math.exp(-((x/(n-1)-s.x)**2+(y/(n-1)-s.y)**2)/(2*s.sigma**2)), 0);
  }));
}

export function predictionVisible(step: number, trainedStep: number): boolean { return step === trainedStep; }
export function methodLabel(method: string): string {
  return ({ numpy_cpu_solver: 'NumPy · CPU solver', torch_cpu_forward: 'PyTorch · CPU forward', torch_cpu_end_to_end: 'PyTorch · CPU end-to-end', torch_cuda_forward: 'CUDA · resident forward', torch_cuda_end_to_end: 'CUDA · end-to-end' } as Record<string, string>)[method] ?? method;
}
