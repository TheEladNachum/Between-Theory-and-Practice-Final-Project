/**
 * The single place that talks to the backend.
 *
 * `analyse` uses Server-Sent Events so the UI can show each analysis stage
 * completing rather than freezing for a minute behind one long POST.
 */

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw await responseError(response);
  return response.json();
}

async function postJSON(url, body) {
  const options = { method: 'POST' };
  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' };
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);
  if (!response.ok) throw await responseError(response);
  return response.json();
}

async function responseError(response) {
  let message = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') message = body.detail;
    else if (typeof body.message === 'string') message = body.message;
  } catch { /* keep the HTTP status when the response is not JSON */ }
  return new Error(message);
}

export const getConfig = () => getJSON('/api/config');
export const saveConfig = (settings) => postJSON('/api/config', settings);
export const testConfig = () => postJSON('/api/config/test');
export const listExamples = () => getJSON('/api/examples');
export const getExample = (id) => getJSON(`/api/examples/${encodeURIComponent(id)}`);

/**
 * Run the full analysis, streaming stage updates.
 *
 * @param {object} incident              The IncidentInput payload.
 * @param {object} handlers
 * @param {(id: string) => void} handlers.onStageStart
 * @param {(id: string) => void} handlers.onStageDone
 * @param {(id: string, message: string) => void} handlers.onStageError
 * @param {(result: object) => void} handlers.onComplete
 * @param {AbortSignal} signal
 */
export async function analyse(incident, handlers, signal) {
  const response = await fetch('/api/analyse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(incident),
    signal,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch { /* response had no JSON body; keep the status line */ }
    throw new Error(detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let split;
    while ((split = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      handleFrame(frame, handlers);
    }
  }
}

function handleFrame(frame, handlers) {
  const dataLines = frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trim());

  if (dataLines.length === 0) return;

  let event;
  try {
    event = JSON.parse(dataLines.join('\n'));
  } catch {
    return; // A malformed frame is not worth killing the run over.
  }

  switch (event.type) {
    case 'stage_start':  handlers.onStageStart?.(event.stage); break;
    case 'stage_done':   handlers.onStageDone?.(event.stage); break;
    case 'stage_error':  handlers.onStageError?.(event.stage, event.message); break;
    case 'complete':     handlers.onComplete?.(event.result); break;
    case 'error':        handlers.onFatal?.(event.message); break;
  }
}
