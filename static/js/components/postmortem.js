/**
 * Postmortem tab.
 *
 * The document is shown as raw Markdown rather than rendered HTML. That is a
 * deliberate choice: this text is meant to be pasted into a real incident
 * tracker, and showing exactly the characters that will be copied avoids the
 * "looks finished because it is nicely formatted" effect the brief warns about.
 */

import { el } from '../dom.js';

export function render(result) {
  const view = el('div', { class: 'view' });

  if (!result.postmortem_markdown) {
    view.append(el('p', { class: 'kv-label', text: 'No postmortem drafted.' }));
    return view;
  }

  const copyBtn = el('button', {
    class: 'btn btn-ghost btn-sm',
    type: 'button',
    text: 'Copy to clipboard',
    onClick: async (event) => {
      const button = event.currentTarget;
      try {
        await navigator.clipboard.writeText(result.postmortem_markdown);
        button.textContent = 'Copied';
      } catch {
        button.textContent = 'Copy failed - select the text manually';
      }
      setTimeout(() => { button.textContent = 'Copy to clipboard'; }, 2000);
    },
  });

  view.append(
    el('div', {
      style: 'display:flex; align-items:center; justify-content:space-between; gap:.5rem;',
    }, [
      el('h3', { class: 'section-title', text: 'Draft postmortem' }),
      copyBtn,
    ]),
    el('p', {
      class: 'kv-label',
      text: 'A draft for a human to edit and sign off. It is not an approved incident record.',
    }),
    el('div', { class: 'markdown-out', text: result.postmortem_markdown }),
  );

  return view;
}
