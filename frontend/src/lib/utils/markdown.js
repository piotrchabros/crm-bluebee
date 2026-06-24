/**
 * Minimal, XSS-safe Markdown -> HTML renderer for the CRM Notes field.
 *
 * Strategy (escape-first): the ENTIRE input is HTML-escaped before any
 * transform runs, so user-supplied tags/scripts can never survive — `<script>`
 * becomes `&lt;script&gt;`. Only a fixed allowlist of tags is then emitted:
 *   h1, h2, p, br, strong, em, ul, ol, li, a
 * Attributes are limited to a safe href (http/https/mailto) plus
 * target/rel on links. There is no path by which raw HTML reaches the DOM,
 * which is why the output is safe to pass to {@html}.
 *
 * Supported syntax: # h1, ## h2, **bold** or __bold__, *italic* or _italic_,
 * dash/star bullet lists, 1. ordered lists, [text](http…) links, blank-line
 * paragraphs, single newlines as <br>, and preserved runs of spaces.
 */

/** @param {string} s */
function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Inline transforms. Runs on already-escaped text, so the only `<`/`>` it can
 * introduce are the fixed tags below.
 * @param {string} s
 */
function inline(s) {
  // Bold first (greedier markers), then italic.
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*(?!\s)([^*\n]+?)\*/g, '$1<em>$2</em>');
  s = s.replace(/(^|[^_])_(?!\s)([^_\n]+?)_/g, '$1<em>$2</em>');
  // Links: [label](url). URL is already escaped; quotes became &quot; so the
  // href attribute cannot be broken out of. Only http(s)/mailto allowed.
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  // Preserve runs of 2+ spaces (single spaces render normally).
  s = s.replace(/ {2,}/g, (m) => '&nbsp;'.repeat(m.length));
  return s;
}

/**
 * Render limited Markdown to sanitized HTML.
 * @param {string} input
 * @returns {string}
 */
export function renderMarkdown(input) {
  if (!input) return '';
  const escaped = escapeHtml(String(input));
  const lines = escaped.split(/\r?\n/);

  /** @type {string[]} */
  const out = [];
  /** @type {string[]} */
  let para = [];
  /** @type {{ tag: 'ul'|'ol', items: string[] } | null} */
  let list = null;

  const flushPara = () => {
    if (para.length) {
      out.push('<p>' + para.map(inline).join('<br>') + '</p>');
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      out.push(
        '<' + list.tag + '>' +
          list.items.map((it) => '<li>' + inline(it) + '</li>').join('') +
          '</' + list.tag + '>'
      );
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '');
    if (!line.trim()) {
      flushPara();
      flushList();
      continue;
    }
    let m;
    if ((m = /^##\s+(.*)$/.exec(line))) {
      flushPara(); flushList();
      out.push('<h2>' + inline(m[1]) + '</h2>');
    } else if ((m = /^#\s+(.*)$/.exec(line))) {
      flushPara(); flushList();
      out.push('<h1>' + inline(m[1]) + '</h1>');
    } else if ((m = /^[-*]\s+(.*)$/.exec(line))) {
      flushPara();
      if (!list || list.tag !== 'ul') { flushList(); list = { tag: 'ul', items: [] }; }
      list.items.push(m[1]);
    } else if ((m = /^\d+\.\s+(.*)$/.exec(line))) {
      flushPara();
      if (!list || list.tag !== 'ol') { flushList(); list = { tag: 'ol', items: [] }; }
      list.items.push(m[1]);
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return out.join('\n');
}
