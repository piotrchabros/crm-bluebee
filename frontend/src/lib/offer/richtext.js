/**
 * Rich-string parsing, ported 1:1 from bluebee-website `blocks.tsx`.
 *
 * A rich string permits ONLY `**bold**` and `[label](url)` (http/https/mailto).
 * Everything else is plain text. Parsing returns tokens that the RichText
 * component renders with normal Svelte markup — never `{@html}` — so raw HTML in
 * the source string is shown as text, never executed. This is the XSS boundary.
 */

const INLINE_TOKEN = /\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)/g;

/**
 * @param {string} s
 * @returns {Array<{type:'text',value:string}|{type:'bold',value:string}|{type:'link',value:string,href:string,external:boolean}>}
 */
export function parseInline(s) {
  /** @type {any[]} */
  const out = [];
  if (s == null) return out;
  s = String(s);
  let last = 0;
  let m;
  INLINE_TOKEN.lastIndex = 0;
  while ((m = INLINE_TOKEN.exec(s)) !== null) {
    if (m.index > last) out.push({ type: 'text', value: s.slice(last, m.index) });
    if (m[1] !== undefined) {
      out.push({ type: 'bold', value: m[1] });
    } else {
      const text = m[2];
      const url = m[3];
      if (/^(https?:|mailto:)/i.test(url)) {
        out.push({ type: 'link', value: text, href: url, external: !/^mailto:/i.test(url) });
      } else {
        // Disallowed scheme → render the label as plain text (drop the link).
        out.push({ type: 'text', value: text });
      }
    }
    last = INLINE_TOKEN.lastIndex;
  }
  if (last < s.length) out.push({ type: 'text', value: s.slice(last) });
  return out;
}

/**
 * Heading orphan fixer, ported from `fixOrphans`: NBSP after one-letter words
 * and gluing the last two words so a lone word never wraps alone.
 * @param {string} s
 */
export function fixOrphans(s) {
  if (s == null) return '';
  let out = String(s).replace(/(^|[\s(])([aiouwzAIOUWZ])\s+/g, (_m, pre, ch) => pre + ch + ' ');
  const i = out.lastIndexOf(' ');
  if (i > 0) out = out.slice(0, i) + ' ' + out.slice(i + 1);
  return out;
}
