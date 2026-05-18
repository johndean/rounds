/**
 * Editor helpers — verbatim port of helpers in docs/port-source/components.jsx
 * (withAlpha, fmtTime, fmtClock). Used everywhere across editor sub-components.
 */

export function withAlpha(hex: string | null | undefined, alphaHex: string): string {
  if (!hex || hex[0] !== '#' || hex.length !== 7) return hex || '#4D6995';
  return hex + alphaHex;
}

export function fmtTime(sec: number | null | undefined): string {
  if (sec == null || isNaN(sec)) return '--:--';
  const s = Math.floor(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s - h * 3600) / 60);
  const ss = s - h * 3600 - m * 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
  return `${m}:${String(ss).padStart(2, '0')}`;
}

export function fmtClock(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: false });
}
