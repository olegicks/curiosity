/**
 * The restricted Markdown subset used by lesson content (docs/spec/02 FR-LRN-2):
 * paragraphs, **bold**, *italic* and "- " bullet lists. Everything else is plain text,
 * and content is never rendered as HTML.
 */

export type Inline = { text: string; bold?: boolean; italic?: boolean };
export type Block = { kind: "paragraph"; inlines: Inline[] } | { kind: "list"; items: Inline[][] };

const BULLET = /^\s*[-*]\s+/;

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  const pattern = /\*\*([^*]+)\*\*|\*([^*]+)\*/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > last) out.push({ text: text.slice(last, index) });
    if (match[1] !== undefined) out.push({ text: match[1], bold: true });
    else if (match[2] !== undefined) out.push({ text: match[2], italic: true });
    last = index + match[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  const chunks = source
    .replace(/\r\n/g, "\n")
    .trim()
    .split(/\n\s*\n/);
  for (const chunk of chunks) {
    const lines = chunk.split("\n").map((l) => l.trimEnd());
    if (lines.length > 0 && lines.every((l) => BULLET.test(l))) {
      blocks.push({ kind: "list", items: lines.map((l) => parseInline(l.replace(BULLET, ""))) });
      continue;
    }
    const text = lines
      .map((l) => l.trim())
      .join(" ")
      .trim();
    if (text) blocks.push({ kind: "paragraph", inlines: parseInline(text) });
  }
  return blocks;
}
