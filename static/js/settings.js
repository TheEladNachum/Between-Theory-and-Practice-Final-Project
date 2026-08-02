/**
 * Browser-based AI configuration.
 *
 * The API key is deliberately write-only: this module sends a new value when
 * the user provides one, but the backend never returns the saved value and the
 * password field is cleared after every save.
 */

import { getConfig, saveConfig, testConfig } from './api.js';
import { $ } from './dom.js';
import { setState } from './state.js';

const PROVIDERS = {
  gemini: {
    host: 'generativelanguage.googleapis.com',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    model: 'gemini-2.5-flash',
  },
  groq: {
    host: 'api.groq.com',
    baseUrl: 'https://api.groq.com/openai/v1',
    model: 'llama-3.3-70b-versatile',
  },
  openrouter: {
    host: 'openrouter.ai',
    baseUrl: 'https://openrouter.ai/api/v1',
    model: 'google/gemini-2.0-flash-exp:free',
  },
  openai: {
    host: 'api.openai.com',
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
  },
  anthropic: {
    host: 'api.anthropic.com',
    baseUrl: 'https://api.anthropic.com/v1/',
    model: 'claude-opus-4-8',
  },
  ollama: {
    host: 'localhost',
    baseUrl: 'http://localhost:11434/v1',
    model: 'llama3.1',
  },
};

let currentConfig = {
  configured: false,
  provider: '',
  model: '',
  base_url: '',
  status: 'loading',
  connection_verified: false,
};

/** Wire the settings dialog, load the safe config, and verify an existing key. */
export async function initSettings() {
  wireDialog();
  setConnectionStatus('checking', 'Checking AI settings...');

  try {
    const config = await getConfig();
    applyConfig(config);

    if (!config.configured) {
      setConnectionStatus(
        'missing',
        'No API key',
        'Open AI settings, paste a key, then save and test the connection.',
      );
      return;
    }

    await verifyConnection();
  } catch (error) {
    setConnectionStatus(
      'failure',
      'Backend unavailable',
      `The configuration could not be loaded: ${error.message}`,
    );
  }
}

function wireDialog() {
  const dialog = $('#settings-dialog');

  $('#settings-open').addEventListener('click', () => {
    populateForm();
    setDialogResult('', '');
    dialog.showModal();
  });

  $('#settings-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });

  $('#settings-provider').addEventListener('change', (event) => {
    const preset = PROVIDERS[event.target.value];
    if (!preset) return;
    $('#settings-base-url').value = preset.baseUrl;
    $('#settings-model').value = preset.model;
  });

  $('#settings-base-url').addEventListener('input', () => {
    $('#settings-provider').value = providerIdFor($('#settings-base-url').value);
  });

  $('#settings-form').addEventListener('submit', saveAndVerify);
  $('#settings-test').addEventListener('click', async () => {
    setBusy(true, 'Testing...');
    try {
      await verifyConnection({ showInDialog: true });
    } finally {
      setBusy(false);
    }
  });
}

function applyConfig(config) {
  currentConfig = {
    ...currentConfig,
    ...config,
    connection_verified: config.status === 'verified',
  };
  setState({ config: { ...currentConfig } });
  updateModelBadge();
  populateForm();
}

function populateForm() {
  $('#settings-provider').value = providerIdFor(currentConfig.base_url);
  $('#settings-base-url').value = currentConfig.base_url || '';
  $('#settings-model').value = currentConfig.model || '';
  $('#settings-api-key').value = '';
  $('#settings-api-key').required = !currentConfig.configured;
  $('#settings-key-hint').textContent = currentConfig.configured
    ? 'A key is saved. Leave this blank to keep it, or paste a replacement.'
    : 'No key is saved. Paste one to configure the AI connection.';
  $('#settings-test').disabled = !currentConfig.configured;
}

function providerIdFor(baseUrl) {
  let hostname = '';
  try {
    hostname = new URL(baseUrl).hostname.toLowerCase();
  } catch { /* an incomplete custom URL stays custom */ }

  for (const [id, preset] of Object.entries(PROVIDERS)) {
    if (hostname === preset.host) return id;
    if (id === 'ollama' && hostname === '127.0.0.1') return id;
  }
  return 'custom';
}

async function saveAndVerify(event) {
  event.preventDefault();

  const apiKey = $('#settings-api-key').value.trim();
  if (!currentConfig.configured && !apiKey) {
    setDialogResult('failure', 'Paste an API key before saving.');
    $('#settings-api-key').focus();
    return;
  }

  const payload = {
    base_url: $('#settings-base-url').value.trim(),
    model: $('#settings-model').value.trim(),
  };
  if (apiKey) payload.api_key = apiKey;

  setBusy(true, 'Saving...');
  setConnectionStatus('checking', 'Saving AI settings...');
  setDialogResult('checking', 'Saving settings locally...');

  try {
    const saved = await saveConfig(payload);
    applyConfig(saved);
    $('#settings-api-key').value = '';
    setDialogResult('checking', 'Settings saved. Testing the provider now...');

    const verified = await verifyConnection({ showInDialog: true });
    if (verified) $('#settings-dialog').close();
  } catch (error) {
    setConnectionStatus('failure', 'Settings could not be saved', error.message);
    setDialogResult('failure', error.message);
  } finally {
    setBusy(false);
  }
}

async function verifyConnection({ showInDialog = false } = {}) {
  if (!currentConfig.configured) {
    const message = 'No API key is saved yet.';
    setConnectionStatus('missing', 'No API key', message);
    if (showInDialog) setDialogResult('failure', message);
    return false;
  }

  setConnectionStatus('checking', 'Checking AI connection...');
  if (showInDialog) setDialogResult('checking', 'Contacting the configured provider...');

  try {
    const result = await testConfig();
    if (!result.ok) {
      const message = result.message || 'The provider rejected the connection.';
      setConnectionStatus('failure', 'AI connection failed', message);
      if (showInDialog) setDialogResult('failure', message);
      return false;
    }

    currentConfig = {
      ...currentConfig,
      provider: result.provider || currentConfig.provider,
      model: result.model || currentConfig.model,
      status: result.status || 'verified',
      connection_verified: true,
    };
    updateModelBadge();
    setConnectionStatus(
      'verified',
      'AI connection verified',
      result.message || `Connected to ${currentConfig.provider}.`,
    );
    if (showInDialog) {
      setDialogResult(
        'verified',
        result.message || `Connected to ${currentConfig.provider} with ${currentConfig.model}.`,
      );
    }
    return true;
  } catch (error) {
    setConnectionStatus('failure', 'AI connection failed', error.message);
    if (showInDialog) setDialogResult('failure', error.message);
    return false;
  }
}

function setConnectionStatus(kind, label, detail = '') {
  const classByKind = {
    verified: 'pill-ok',
    checking: 'pill-warn',
    missing: 'pill-danger',
    failure: 'pill-danger',
  };
  const pill = $('#config-status');
  pill.className = `pill config-status ${classByKind[kind] || 'pill-warn'}`;
  pill.textContent = label;
  pill.title = detail;

  const detailNode = $('#config-detail');
  detailNode.textContent = detail;
  detailNode.hidden = !detail;
  detailNode.className = `config-detail${kind === 'failure' || kind === 'missing' ? ' is-danger' : ''}`;

  currentConfig = {
    ...currentConfig,
    status: kind,
    connection_verified: kind === 'verified',
  };
  setState({ config: { ...currentConfig } });
}

function setDialogResult(kind, message) {
  const node = $('#settings-result');
  node.hidden = !message;
  node.textContent = message;
  node.className = `settings-result${kind ? ` is-${kind}` : ''}`;
}

function setBusy(busy, label = 'Save & test connection') {
  const saveButton = $('#settings-save');
  saveButton.disabled = busy;
  saveButton.textContent = busy ? label : 'Save & test connection';
  $('#settings-test').disabled = busy || !currentConfig.configured;
  $('#settings-close').disabled = busy;
}

function updateModelBadge() {
  const provider = currentConfig.provider || 'AI provider';
  const model = currentConfig.model || 'model not set';
  $('#model-badge').textContent = `${provider} - ${model}`;
}
