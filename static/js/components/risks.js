/** Reasoning-risks tab: biases and fallacies this investigation is exposed to. */

import { el } from '../dom.js';

export function render(result) {
  const view = el('div', { class: 'view' });

  view.append(
    el('div', {}, [
      el('h3', { class: 'section-title' }, [
        'Reasoning risks',
        el('span', { class: 'pill pill-warn', text: `${result.reasoning_risks.length} flagged` }),
      ]),
      el('p', {
        class: 'kv-label',
        text: 'These are risks in how this investigation was conducted, not findings about the system.',
      }),
    ]),
  );

  if (result.unverified_citations?.length) {
    view.append(unverifiedPanel(result.unverified_citations));
  }

  if (!result.reasoning_risks.length) {
    view.append(el('p', { class: 'kv-label', text: 'No reasoning risks were flagged.' }));
    return view;
  }

  for (const risk of result.reasoning_risks) {
    view.append(riskCard(risk));
  }

  return view;
}

function riskCard(risk) {
  return el('article', { class: 'card' }, [
    el('div', { class: 'card-head' }, [
      el('div', { class: 'card-title', text: risk.bias_name }),
      el('span', { class: 'pill pill-muted', text: risk.bias_id }),
    ]),
    el('div', { class: 'card-body' }, [
      el('div', { class: 'kv' }, [
        el('span', { class: 'kv-label', text: 'Where it shows up here' }),
        el('span', { text: risk.where_it_appears }),
      ]),
      el('div', { class: 'kv' }, [
        el('span', { class: 'kv-label', text: 'Why it matters' }),
        el('span', { text: risk.why_it_matters }),
      ]),
      el('div', { class: 'kv' }, [
        el('span', { class: 'kv-label', text: 'How to reduce it' }),
        el('span', { text: risk.mitigation }),
      ]),
    ]),
  ]);
}

/**
 * Citations whose quoted text was not found in the input the model named.
 * This is the tool auditing its own output, so it gets the loudest treatment.
 */
function unverifiedPanel(refs) {
  return el('article', { class: 'card' }, [
    el('div', { class: 'card-head' }, [
      el('div', { class: 'card-title', text: 'Unverified citations' }),
      el('span', { class: 'pill pill-danger', text: `${refs.length} found` }),
    ]),
    el('div', { class: 'card-body' }, [
      el('p', {
        text:
          'The model quoted these as evidence, but the quoted text could not be '
          + 'located in the source it named. Treat every claim resting on them as '
          + 'unsupported until you check it yourself.',
      }),
      el('ul', { class: 'evidence-list' }, refs.map((ref) =>
        el('li', { class: 'evidence is-unverified' }, [
          el('span', { class: 'evidence-source', text: `claimed source: ${ref.source}` }),
          el('span', { class: 'evidence-quote', text: `"${ref.quote}"` }),
        ]),
      )),
    ]),
  ]);
}
