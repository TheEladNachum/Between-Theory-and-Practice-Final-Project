/**
 * The single place that talks to the backend.
 *
 * `analyse` uses Server-Sent Events so the UI can show each analysis stage
 * completing rather than freezing for a minute behind one long POST.
 */

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

export const getConfig = () => getJSON('/api/config');
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
