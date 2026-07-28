/**
 * Generated fallback texture (§21). Built with an offscreen canvas — no binary
 * image files. Shows an "UNKNOWN"/"?" placeholder so a missing asset or unknown
 * kind never crashes the scene. Colour is NOT the only cue (has "?" text).
 *
 * Pixi is imported lazily (dynamic) so pure unit tests can exercise the drawing
 * spec via `fallbackSpec()` without a WebGL context.
 */

import { Texture } from 'pixi.js';

export interface FallbackSpec {
  width: number;
  height: number;
  glyph: string;
  label: string;
  bg: string;
  fg: string;
}

export function fallbackSpec(label = 'UNKNOWN'): FallbackSpec {
  return { width: 96, height: 96, glyph: '?', label, bg: '#8b98a6', fg: '#1b2b3a' };
}

/** Draw the fallback onto a 2D canvas (testable without WebGL). */
export function drawFallback(canvas: HTMLCanvasElement, spec: FallbackSpec): void {
  canvas.width = spec.width;
  canvas.height = spec.height;
  let ctx: CanvasRenderingContext2D | null = null;
  try {
    ctx = canvas.getContext('2d');
  } catch {
    ctx = null; // jsdom without the canvas package throws here — treat as no ctx.
  }
  if (!ctx) return;
  ctx.fillStyle = spec.bg;
  ctx.fillRect(0, 0, spec.width, spec.height);
  ctx.strokeStyle = spec.fg;
  ctx.lineWidth = 3;
  ctx.setLineDash([6, 4]); // dashed = non-colour "unknown" cue
  ctx.strokeRect(4, 4, spec.width - 8, spec.height - 8);
  ctx.fillStyle = spec.fg;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = 'bold 36px monospace';
  ctx.fillText(spec.glyph, spec.width / 2, spec.height / 2 - 8);
  ctx.font = 'bold 12px monospace';
  ctx.fillText(spec.label, spec.width / 2, spec.height - 16);
}

/**
 * Create a Pixi Texture for the fallback. Returns null if a canvas/texture can't
 * be created (never throws — the scene draws a Graphics placeholder instead).
 */
export function createFallbackTexture(spec: FallbackSpec = fallbackSpec()): Texture | null {
  try {
    if (typeof document === 'undefined') return null;
    const canvas = document.createElement('canvas');
    drawFallback(canvas, spec);
    return Texture.from(canvas);
  } catch {
    return null;
  }
}
