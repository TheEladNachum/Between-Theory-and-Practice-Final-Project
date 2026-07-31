/**
 * Tiny DOM helpers.
 *
 * Everything the UI renders comes from model output, so nothing here ever
 * assigns to innerHTML with untrusted content - `el()` sets text via
 * textContent, which makes injection impossible by construction.
 */

/** Create an element. `attrs.class`, `attrs.text`, `attrs.dataset` are special. */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;

    if (key === 'class') {
      node.className = value;
    } else if (key === 'text') {
      node.textContent = value;
    } else if (key === 'dataset') {
      Object.assign(node.dataset, value);
    } else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) {
      node.setAttribute(key, '');
    } else {
      node.setAttribute(key, value);
    }
  }

  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function show(node, visible = true) {
  node.hidden = !visible;
}

/** Human-readable label for an evidence source key. */
const SOURCE_LABELS = {
  description: 'reported description',
  logs: 'application logs',
  error_traces: 'error traces',
  alerts: 'monitoring alerts',
  deployment_notes: 'deployment notes',
  user_reports: 'user reports',
  extra: 'other evidence',
};

export const sourceLabel = (key) => SOURCE_LABELS[key] ?? key;

/** Render an evidence citation block. */
export function evidenceItem(ref, variant = '') {
  const classes = ['evidence', variant].filter(Boolean).join(' ');
  return el('li', { class: classes }, [
    el('span', { class: 'evidence-source' }, [
      sourceLabel(ref.source),
      ref.unverified ? el('span', { class: 'pill pill-danger', text: 'not found in input' }) : null,
    ]),
    el('span', { class: 'evidence-quote', text: `"${ref.quote}"` }),
  ]);
}

/** Render a list of citations, or a small note when there are none. */
export function evidenceList(refs, variant = '', emptyNote = 'No evidence cited.') {
  if (!refs || refs.length === 0) {
    return el('p', { class: 'kv-label', text: emptyNote });
  }
  return el('ul', { class: 'evidence-list' }, refs.map((r) => evidenceItem(r, variant)));
}

/** A labelled block of text. */
export function kv(label, value) {
  return el('div', { class: 'kv' }, [
    el('span', { class: 'kv-label', text: label }),
    el('span', { text: value }),
  ]);
}
