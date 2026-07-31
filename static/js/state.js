/**
 * A minimal observable store.
 *
 * The whole app reads from one object and re-renders on change. This is far
 * less machinery than a framework, and it keeps every view function pure:
 * `render(state) -> DOM`, with no component holding its own copy of the data.
 */

const listeners = new Set();

const state = {
  /** 'idle' | 'running' | 'done' | 'error' */
  status: 'idle',
  /** Which result tab is showing. */
  view: 'summary',
  /** The AnalysisResult returned by the backend, or null. */
  result: null,
  /** Per-stage progress: { id, label, state: 'pending'|'running'|'done'|'failed' } */
  stages: [],
  /** Strings shown in the warning strip. */
  warnings: [],
  /** Fatal error message, or null. */
  error: null,
  /** Backend config info, filled in at startup. */
  config: { configured: false, model: '', effort: '' },
};

export function getState() {
  return state;
}

export function setState(patch) {
  Object.assign(state, patch);
  for (const fn of listeners) fn(state);
}

export function subscribe(fn) {
  listeners.add(fn);
  fn(state);
  return () => listeners.delete(fn);
}

/** Update one stage in place without replacing the whole array identity. */
export function setStage(id, stageState) {
  const stage = state.stages.find((s) => s.id === id);
  if (stage) {
    stage.state = stageState;
    setState({ stages: [...state.stages] });
  }
}

export const STAGE_LABELS = [
  { id: 'summary', label: 'Summary & facts' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'hypotheses', label: 'Hypotheses' },
  { id: 'reasoning_risks', label: 'Reasoning risks' },
  { id: 'actions', label: 'Next actions' },
  { id: 'postmortem', label: 'Postmortem' },
];

export function freshStages() {
  return STAGE_LABELS.map((s) => ({ ...s, state: 'pending' }));
}
