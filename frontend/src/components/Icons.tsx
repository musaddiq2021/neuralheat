import type { CSSProperties } from 'react';

const paths: Record<string, string> = {
  grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  heat: 'M8 3c-3 5 3 5 0 10s-3 7 1 8 M15 3c-3 5 3 5 0 10s-3 7 1 8',
  network: 'M4 4h5v5H4z M15 4h5v5h-5z M9 16h6v5H9z M6.5 9v3h11V9 M12 12v4',
  terminal: 'm4 6 5 5-5 5 M12 17h8', chart: 'M3 3v18h18 M6 15l4-5 4 3 6-8',
  play: 'm8 5 11 7-11 7z', pause: 'M8 5v14 M16 5v14', reset: 'M4 10a8 8 0 1 1 1 9 M4 4v6h6',
  plus: 'M12 5v14 M5 12h14', close: 'm6 6 12 12 M18 6 6 18', arrow: 'M5 12h14 m-5-5 5 5-5 5',
  cpu: 'M7 7h10v10H7z M9 1v4 M15 1v4 M9 19v4 M15 19v4 M1 9h4 M1 15h4 M19 9h4 M19 15h4',
  cube: 'm12 3 9 5v9l-9 5-9-5V8z M3 8l9 5 9-5 M12 13v9',
  check: 'm5 12 4 4L19 6', info: 'M12 11v6 M12 7v.1 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  chevron: 'm9 5 7 7-7 7', folder: 'M3 5h6l2 3h10v12H3z', download: 'M12 3v12 m-5-5 5 5 5-5 M4 17v4h16v-4',
  menu: 'M4 6h16 M4 12h16 M4 18h16', bolt: 'm13 2-9 12h7l-1 8L21 9h-8z',
};
export default function Icon({ name, size = 18, style }: { name: string; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name] ?? paths.info}/></svg>;
}
