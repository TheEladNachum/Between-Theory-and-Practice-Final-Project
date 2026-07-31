/**
 * Hypotheses tab.
 *
 * The evidence-for and evidence-against columns sit side by side deliberately:
 * a hypothesis with nothing in the "against" column is the visual signature of
 * confirmation bias, and putting the empty box next to the full one makes that
 * obvious without needing a warning message.
 */

import { el, evidenceList } from '../dom.js';

const CONFIDENCE_PILL = {
  high: 'pill-danger',
  medium: 'pill-warn',
  low: 'pill-muted',
};

export function render(result) {
  const view = el('div', { class: 'view' });

  if (!result.hypotheses.length) {
    view.append(el('p', { class: 'kv-label', text: 'No hypotheses generated.' }));
    return view;
  }

  view.append(
    el('div', {}, [
      el('h3', { class: 'section-title' }, [
        'Candidate root causes',
        el('span', { class: 'pill pill-accent', text: `${result.hypotheses.length} competing` }),
      ]),
      el('p', {
        class: 'kv-label',
        text: 'None of these is a conclusion. Each one names a test that would settle it.',
      }),
    ]),
  );

  result.hypotheses.forEach((hypothesis, index) => {
    view.append(hypothesisCard(hypothesis, index + 1));
  });

  return view;
}

function hypothesisCard(hypothesis, rank) {
  const noCounterEvidence = !hypothesis.contradicting_evidence?.length;

  return el('article', { class: 'card' }, [
    el('div', { class: 'card-head' }, [
      el('div', { class: 'card-title', text: `${rank}. ${hypothesis.title}` }),
      el('span', {
        class: `pill ${CONFIDENCE_PILL[hypothesis.confidence] ?? 'pill-muted'}`,
        text: `${hypothesis.confidence} confidence`,
      }),
    ]),
    el('div', { class: 'card-body' }, [
      el('p', { text: hypothesis.explanation }),

      el('div', { class: 'kv' }, [
        el('span', { class: 'kv-label', text: 'Why this confidence level' }),
        el('span', { text: hypothesis.confidence_reason }),
      ]),

      el('div', { class: 'kv' }, [
        el('span', { class: 'kv-label', text: 'Evidence for' }),
        evidenceList(hypothesis.supporting_evidence, 'is-for', 'Nothing cited in support.'),
      ]),

      el('div', { class: 'kv' }, [
        el('span', { class: 'kv-label' }, [
          'Evidence against',
          noCounterEvidence
            ? el('span', { class: 'pill pill-warn', text: 'none found - possible confirmation bias' })
            : null,
        ]),
        evidenceList(
          hypothesis.contradicting_evidence,
          'is-against',
          'No contradicting evidence was found. Check whether any was looked for.',
        ),
      ]),

      el('div', { class: 'kv' }, [
        el('span', { class: 'kv-label', text: 'Test that would settle it' }),
        el('span', { text: hypothesis.recommended_test }),
      ]),
    ]),
  ]);
}
