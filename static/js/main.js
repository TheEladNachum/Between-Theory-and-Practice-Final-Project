/**
 * Application entry point: wiring only.
 *
 * Every piece of rendering lives in ./components, every network call in
 * ./api.js, and all shared data in ./state.js. This file connects them and
 * owns nothing else.
 */

import { $, $$, clear, el, show } from './dom.js';
import { analyse, getExample, listExamples } from './api.js';
import { freshStages, getState, setStage, setState, subscribe } from './state.js';
import { download } from './report.js';
import { initSettings } from './settings.js';

import * as summaryView from './components/summary.js';
import * as timelineView from './components/timeline.js';
import * as hypothesesView from './components/hypotheses.js';
import * as risksView from './components/risks.js';
import * as actionsView from './components/actions.js';
import * as postmortemView from './components/postmortem.js';

const VIEWS = {
  summary: summaryView,
  timeline: timelineView,
  hypotheses: hypothesesView,
  risks: risksView,
  actions: actionsView,
  postmortem: postmortemView,
};

/** The textarea ids, in the order they map onto IncidentInput fields. */
const FIELDS = [
  'title', 'description', 'logs', 'error_traces',
  'alerts', 'deployment_notes', 'user_reports', 'extra',
];

let controller = null;

// --------------------------------------------------------------------------
// Boot
// --------------------------------------------------------------------------

init();

async function init() {
  restoreTheme();
  wireTheme();
  wireEvidenceTabs();
  wireResultTabs();
  wireFileInputs();
  wireCharCounts();
  wireForm();
  wireExport();
  wireClear();

  subscribe(renderApp);

  await Promise.all([initSettings(), loadExamples()]);
}

// --------------------------------------------------------------------------
// Startup data
// --------------------------------------------------------------------------

async function loadExamples() {
  const select = $('#example-select');
  try {
    const { examples } = await listExamples();
    for (const example of examples) {
      select.append(el('option', { value: example.id, text: example.name }));
    }
  } catch {
    select.disabled = true;
  }

  select.addEventListener('change', async () => {
    if (!select.value) return;
    try {
      const incident = await getExample(select.value);
      for (const field of FIELDS) {
        const input = $(`#f-${field}`);
        if (input) input.value = incident[field] ?? '';
      }
      refreshCharCounts();
      refreshTabDots();
    } catch {
      pushWarning('That example could not be loaded.');
    }
    select.value = '';
  });
}

// --------------------------------------------------------------------------
// Form
// --------------------------------------------------------------------------

function collectIncident() {
  const incident = {};
  for (const field of FIELDS) {
    incident[field] = ($(`#f-${field}`)?.value ?? '').trim();
  }
  if (!incident.title) incident.title = 'Untitled incident';
  return incident;
}

function wireForm() {
  $('#incident-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await runAnalysis();
  });

  $('#cancel-btn').addEventListener('click', () => {
    controller?.abort();
    controller = null;
    setState({ status: 'idle' });
  });
}

async function runAnalysis() {
  const incident = collectIncident();

  const hasEvidence = FIELDS.slice(1).some((field) => incident[field]);
  if (!hasEvidence) {
    pushWarning('Add some evidence before running the analysis - even a short description will do.');
    return;
  }

  controller = new AbortController();
  setState({
    status: 'running',
    result: null,
    error: null,
    warnings: [],
    stages: freshStages(),
  });

  try {
    await analyse(incident, {
      onStageStart: (id) => setStage(id, 'running'),
      onStageDone: (id) => setStage(id, 'done'),
      onStageError: (id, message) => {
        setStage(id, 'failed');
        pushWarning(`Stage "${id}" failed: ${message}`);
      },
      onComplete: (result) => setState({ result, status: 'done', view: 'summary' }),
      onFatal: (message) => setState({ status: 'error', error: message }),
    }, controller.signal);
  } catch (error) {
    if (error.name === 'AbortError') return;
    setState({ status: 'error', error: error.message });
  } finally {
    controller = null;
  }
}

function wireClear() {
  $('#clear-btn').addEventListener('click', () => {
    for (const field of FIELDS) {
      const input = $(`#f-${field}`);
      if (input) input.value = '';
    }
    refreshCharCounts();
    refreshTabDots();
    setState({ result: null, status: 'idle', warnings: [], error: null, stages: [] });
  });
}

// --------------------------------------------------------------------------
// Tabs, files, counters
// --------------------------------------------------------------------------

function wireEvidenceTabs() {
  for (const tab of $$('.etab')) {
    tab.addEventListener('click', () => {
      $$('.etab').forEach((t) => t.classList.toggle('is-active', t === tab));
      $$('.epane').forEach((p) => p.classList.toggle('is-active', p.id === tab.dataset.target));
    });
  }
}

function wireResultTabs() {
  for (const tab of $$('.rtab')) {
    tab.addEventListener('click', () => setState({ view: tab.dataset.view }));
  }
}

function wireFileInputs() {
  for (const input of $$('input[type="file"]')) {
    input.addEventListener('change', async () => {
      const file = input.files?.[0];
      if (!file) return;

      // 2 MB is far more than any realistic log excerpt, and keeps the request
      // well inside the model's context window.
      if (file.size > 2 * 1024 * 1024) {
        pushWarning(`${file.name} is larger than 2 MB. Paste the relevant excerpt instead.`);
        input.value = '';
        return;
      }

      const target = $(`#${input.dataset.targetField}`);
      const text = await file.text();
      target.value = target.value ? `${target.value}\n\n${text}` : text;
      input.value = '';
      refreshCharCounts();
      refreshTabDots();
    });
  }
}

function wireCharCounts() {
  for (const field of FIELDS) {
    $(`#f-${field}`)?.addEventListener('input', () => {
      refreshCharCounts();
      refreshTabDots();
    });
  }
  refreshCharCounts();
}

function refreshCharCounts() {
  for (const counter of $$('.byte-count')) {
    const source = $(`#${counter.dataset.countFor}`);
    const length = source?.value.length ?? 0;
    counter.textContent = `${length.toLocaleString()} characters`;
  }
}

/** Put a green dot on evidence tabs that have content, so nothing gets missed. */
function refreshTabDots() {
  const paneField = {
    'pane-logs': 'logs',
    'pane-traces': 'error_traces',
    'pane-alerts': 'alerts',
    'pane-deploy': 'deployment_notes',
    'pane-users': 'user_reports',
    'pane-extra': 'extra',
  };
  for (const tab of $$('.etab')) {
    const field = paneField[tab.dataset.target];
    const filled = Boolean($(`#f-${field}`)?.value.trim());
    tab.dataset.filled = filled ? 'yes' : 'no';
  }
}

function wireExport() {
  $('#export-btn').addEventListener('click', () => {
    const { result } = getState();
    if (result) download(result);
  });
}

// --------------------------------------------------------------------------
// Theme
// --------------------------------------------------------------------------

function restoreTheme() {
  const stored = localStorage.getItem('incidentiq-theme');
  const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.theme = stored ?? preferred;
  updateThemeIcon();
}

function wireTheme() {
  $('#theme-toggle').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('incidentiq-theme', next);
    updateThemeIcon();
  });
}

function updateThemeIcon() {
  const icon = $('[data-theme-icon]');
  icon.textContent = document.documentElement.dataset.theme === 'dark' ? '☀' : '☽';
}

// --------------------------------------------------------------------------
// Rendering
// --------------------------------------------------------------------------

function pushWarning(message, danger = false) {
  const { warnings } = getState();
  setState({ warnings: [...warnings, { message, danger }] });
}

function renderApp(state) {
  renderProgress(state);
  renderWarnings(state);
  renderResults(state);

  $('#analyse-btn').disabled = state.status === 'running' || !state.config.connection_verified;
  $('#analyse-btn').textContent = state.status === 'running' ? 'Analysing…' : 'Analyse incident';
  show($('#cancel-btn'), state.status === 'running');
  $('#export-btn').disabled = !state.result;
}

function renderProgress(state) {
  const container = $('#progress');
  const list = clear($('#progress-steps'));
  show(container, state.stages.length > 0);

  for (const stage of state.stages) {
    list.append(
      el('li', { dataset: { state: stage.state } }, [
        stage.state === 'running' ? el('span', { class: 'spinner' }) : null,
        stage.label,
      ]),
    );
  }
}

function renderWarnings(state) {
  const container = clear($('#warnings'));
  const entries = [...state.warnings];

  if (state.error) {
    entries.unshift({ message: state.error, danger: true });
  }
  if (state.result?.warnings?.length) {
    for (const warning of state.result.warnings) {
      entries.push({ message: warning, danger: false });
    }
  }

  show(container, entries.length > 0);
  for (const entry of entries) {
    container.append(
      el('div', { class: `warning${entry.danger ? ' is-danger' : ''}` }, [
        el('span', { text: entry.danger ? '⚠' : 'ℹ' }),
        el('span', { text: entry.message }),
      ]),
    );
  }
}

function renderResults(state) {
  const body = $('#results-body');
  const tabs = $('#result-tabs');

  if (!state.result) {
    show(tabs, false);
    if (!$('#empty-state')) {
      clear(body).append(emptyState());
    }
    return;
  }

  show(tabs, true);
  updateTabCounts(state.result);

  for (const tab of $$('.rtab')) {
    tab.classList.toggle('is-active', tab.dataset.view === state.view);
  }

  const view = VIEWS[state.view] ?? summaryView;
  clear(body).append(view.render(state.result));
  body.scrollTop = 0;
}

function updateTabCounts(result) {
  const counts = {
    hypotheses: result.hypotheses.length,
    risks: result.reasoning_risks.length,
    actions: result.actions.length,
    timeline: result.timeline.length,
  };
  for (const tab of $$('.rtab')) {
    const count = counts[tab.dataset.view];
    if (count) tab.dataset.count = count;
    else delete tab.dataset.count;
  }
}

function emptyState() {
  return el('div', { class: 'empty-state', id: 'empty-state' }, [
    el('div', { class: 'empty-mark' }),
    el('h3', { text: 'No investigation yet' }),
    el('p', { text: 'Paste evidence on the left, or load one of the example incidents, then run the analysis.' }),
  ]);
}
