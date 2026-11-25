import { PDFDocument } from "pdf-lib";

const A4 = { w: 595.28, h: 841.89 };

/** Stitch JPEG pages into one PDF client-side; each page is fitted onto A4 (portrait or landscape). */
export async function stitchPdf(pages: { jpeg: Blob; width: number; height: number }[], title: string): Promise<Blob> {
  const pdf = await PDFDocument.create();
  pdf.setTitle(title);
  pdf.setProducer("InaiFlow scanner");
  for (const p of pages) {
    const img = await pdf.embedJpg(new Uint8Array(await p.jpeg.arrayBuffer()));
    const landscape = p.width > p.height;
    const pw = landscape ? A4.h : A4.w;
    const ph = landscape ? A4.w : A4.h;
    const scale = Math.min(pw / p.width, ph / p.height);
    const w = p.width * scale;
    const h = p.height * scale;
    const page = pdf.addPage([pw, ph]);
    page.drawImage(img, { x: (pw - w) / 2, y: (ph - h) / 2, width: w, height: h });
  }
  const bytes = await pdf.save();
  return new Blob([bytes as BlobPart], { type: "application/pdf" });
}
