/** Summary tab: prose summary, then Facts and Assumptions kept visually apart. */

import { el, evidenceList } from '../dom.js';

export function render(result) {
  const view = el('div', { class: 'view' });

  view.append(
    el('div', {}, [
      el('h3', { class: 'section-title', text: 'What happened' }),
      el('div', { class: 'prose' }, [el('p', { text: result.summary || 'No summary produced.' })]),
    ]),
  );

  view.append(
    el('div', {}, [
      el('h3', { class: 'section-title' }, [
        'Facts',
        el('span', { class: 'pill pill-ok', text: 'supported by the input' }),
      ]),
      result.facts.length
        ? el('div', { class: 'stack' }, result.facts.map(factCard))
        : el('p', { class: 'kv-label', text: 'No facts extracted.' }),
    ]),
  );

  view.append(
    el('div', {}, [
      el('h3', { class: 'section-title' }, [
        'Assumptions',
        el('span', { class: 'pill pill-warn', text: 'believed, not proven' }),
      ]),
      result.assumptions.length
        ? el('div', { class: 'stack' }, result.assumptions.map(assumptionCard))
        : el('p', { class: 'kv-label', text: 'No assumptions recorded.' }),
    ]),
  );

  return view;
}

function factCard(fact) {
  return el('div', { class: 'item' }, [
    el('div', { class: 'item-lead', text: fact.statement }),
    evidenceList(fact.evidence, '', 'No citation - treat this as an assumption.'),
  ]);
}

function assumptionCard(assumption) {
  return el('div', { class: 'item' }, [
    el('div', { class: 'item-lead', text: assumption.statement }),
    el('div', { class: 'kv' }, [
      el('span', { class: 'kv-label', text: 'Why it is unproven' }),
      el('span', { text: assumption.why_unproven }),
    ]),
    el('div', { class: 'kv' }, [
      el('span', { class: 'kv-label', text: 'How to verify' }),
      el('span', { text: assumption.how_to_verify }),
    ]),
  ]);
}
