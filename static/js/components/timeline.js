/** Timeline tab. Inferred events are marked so the reader can discount them. */

import { el, evidenceList } from '../dom.js';

export function render(result) {
  const view = el('div', { class: 'view' });

  if (!result.timeline.length) {
    view.append(el('p', { class: 'kv-label', text: 'No timeline could be reconstructed.' }));
    return view;
  }

  const inferredCount = result.timeline.filter((e) => e.inferred).length;

  view.append(
    el('div', {}, [
      el('h3', { class: 'section-title' }, [
        'Reconstructed timeline',
        inferredCount
          ? el('span', {
              class: 'pill pill-warn',
              text: `${inferredCount} inferred`,
            })
          : null,
      ]),
      el('p', {
        class: 'kv-label',
        text: 'Solid markers were read directly from the evidence. Dashed markers were deduced.',
      }),
    ]),
  );

  view.append(
    el('ol', { class: 'timeline' }, result.timeline.map(eventItem)),
  );

  return view;
}

function eventItem(event) {
  return el('li', { dataset: { inferred: String(event.inferred) } }, [
    el('div', { class: 'tl-time' }, [
      event.timestamp || 'unknown time',
      event.inferred ? el('span', { class: 'pill pill-warn', text: 'inferred' }) : null,
    ]),
    el('div', { class: 'tl-desc', text: event.description }),
    evidenceList(event.evidence, '', 'No source cited for this event.'),
  ]);
}
