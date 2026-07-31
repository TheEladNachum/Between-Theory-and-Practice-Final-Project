/** Actions tab: what to do next, plus what the evidence cannot answer. */

import { el } from '../dom.js';

const PRIORITY_PILL = {
  immediate: 'pill-danger',
  soon: 'pill-warn',
  later: 'pill-muted',
};

const PRIORITY_ORDER = { immediate: 0, soon: 1, later: 2 };

export function render(result) {
  const view = el('div', { class: 'view' });

  const actions = [...result.actions].sort(
    (a, b) => (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9),
  );

  view.append(
    el('div', {}, [
      el('h3', { class: 'section-title', text: 'Recommended next steps' }),
      actions.length
        ? el('div', { class: 'stack' }, actions.map(actionItem))
        : el('p', { class: 'kv-label', text: 'No actions recommended.' }),
    ]),
  );

  view.append(
    el('div', {}, [
      el('h3', { class: 'section-title' }, [
        'Still unknown',
        el('span', { class: 'pill pill-muted', text: `${result.open_questions.length} open` }),
      ]),
      el('p', {
        class: 'kv-label',
        text: 'Questions the available evidence cannot settle. These bound how far the analysis can be trusted.',
      }),
      result.open_questions.length
        ? el('div', { class: 'stack' }, result.open_questions.map(questionItem))
        : el('p', { class: 'kv-label', text: 'No open questions recorded - which is itself suspicious.' }),
    ]),
  );

  return view;
}

function actionItem(action) {
  return el('div', { class: 'item' }, [
    el('div', {
      style: 'display:flex; gap:.5rem; align-items:flex-start; justify-content:space-between;',
    }, [
      el('span', { class: 'item-lead', text: action.step }),
      el('span', {
        class: `pill ${PRIORITY_PILL[action.priority] ?? 'pill-muted'}`,
        text: action.priority,
      }),
    ]),
    el('div', { class: 'kv' }, [
      el('span', { class: 'kv-label', text: 'Why' }),
      el('span', { text: action.rationale }),
    ]),
    action.linked_hypothesis
      ? el('div', { class: 'kv' }, [
          el('span', { class: 'kv-label', text: 'Tests hypothesis' }),
          el('span', { text: action.linked_hypothesis }),
        ])
      : null,
  ]);
}

function questionItem(question) {
  return el('div', { class: 'item' }, [
    el('div', { class: 'item-lead', text: question.question }),
    el('div', { class: 'kv' }, [
      el('span', { class: 'kv-label', text: 'Why it matters' }),
      el('span', { text: question.why_it_matters }),
    ]),
  ]);
}
