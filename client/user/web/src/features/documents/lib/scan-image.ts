/** Canvas helpers for the camera scanner: rotate, crop (by margins %), contrast enhancement. */
export interface PageEdit {
  rotation: 0 | 90 | 180 | 270;
  /** Margins to cut, in % of width/height. */
  crop: { top: number; right: number; bottom: number; left: number };
  enhance: boolean;
}

export const DEFAULT_EDIT: PageEdit = { rotation: 0, crop: { top: 0, right: 0, bottom: 0, left: 0 }, enhance: true };

const MAX_SIDE = 2000;

/** Render `source` with the edit applied; output capped at 2000 px on the long side. */
export function renderPage(source: CanvasImageSource & { width: number; height: number }, edit: PageEdit): HTMLCanvasElement {
  const { top, right, bottom, left } = edit.crop;
  const sx = (source.width * left) / 100;
  const sy = (source.height * top) / 100;
  const sw = Math.max(1, source.width * (1 - (left + right) / 100));
  const sh = Math.max(1, source.height * (1 - (top + bottom) / 100));
  const scale = Math.min(1, MAX_SIDE / Math.max(sw, sh));
  const w = Math.round(sw * scale);
  const h = Math.round(sh * scale);
  const swap = edit.rotation === 90 || edit.rotation === 270;
  const canvas = document.createElement("canvas");
  canvas.width = swap ? h : w;
  canvas.height = swap ? w : h;
  const ctx = canvas.getContext("2d")!;
  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.rotate((edit.rotation * Math.PI) / 180);
  ctx.drawImage(source, sx, sy, sw, sh, -w / 2, -h / 2, w, h);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  if (edit.enhance) enhance(ctx, canvas.width, canvas.height);
  return canvas;
}

/** Grayscale + percentile contrast stretch — makes paper white and ink dark. */
function enhance(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  const hist = new Uint32Array(256);
  for (let i = 0; i < d.length; i += 4) {
    const g = (d[i]! * 299 + d[i + 1]! * 587 + d[i + 2]! * 114) / 1000;
    d[i] = g;
    hist[Math.round(g)]!++;
  }
  const total = w * h;
  let lo = 0, hi = 255, acc = 0;
  for (let v = 0; v < 256; v++) { acc += hist[v]!; if (acc > total * 0.02) { lo = v; break; } }
  acc = 0;
  for (let v = 255; v >= 0; v--) { acc += hist[v]!; if (acc > total * 0.05) { hi = v; break; } }
  const range = Math.max(1, hi - lo);
  for (let i = 0; i < d.length; i += 4) {
    const v = Math.max(0, Math.min(255, ((d[i]! - lo) * 255) / range));
    d[i] = d[i + 1] = d[i + 2] = v;
  }
  ctx.putImageData(img, 0, 0);
}

export function canvasToJpeg(canvas: HTMLCanvasElement, quality = 0.82): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Could not encode page"))), "image/jpeg", quality));
}

export function loadImage(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Not an image")); };
    img.src = url;
  });
}
