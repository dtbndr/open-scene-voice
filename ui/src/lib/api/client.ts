// The one typed client every screen uses (U6). URLs come only from validated project ids and key-name constants.
import { ApiError, FIXED_MESSAGE, NetworkError, notifyStaleLink } from './errors';
import type {
  Catalog,
  BeatsDocument,
  CheckAnswer,
  CreatedProject,
  CurrentJob,
  KeyName,
  KeysView,
  ProjectDetail,
  ProjectList,
  ScriptText,
  StartBody
} from './types';

async function request<T>(method: 'GET' | 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin' };
  if (method === 'POST' || method === 'PUT') {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body ?? {});
  }
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new NetworkError();
  }
  let parsed: unknown = null;
  try {
    parsed = await response.json();
  } catch {
    parsed = null;
  }
  if (response.ok) return parsed as T;
  const error = envelope(parsed);
  const failure = error
    ? new ApiError(response.status, error.kind, error.message)
    : new ApiError(response.status, 'internal_error', FIXED_MESSAGE);
  if (response.status === 401 && failure.kind === 'stale_link') notifyStaleLink();
  throw failure;
}

function envelope(value: unknown): { kind: string; message: string } | null {
  if (typeof value !== 'object' || value === null) return null;
  const inner = (value as { error?: unknown }).error;
  if (typeof inner !== 'object' || inner === null) return null;
  const { kind, message } = inner as { kind?: unknown; message?: unknown };
  return typeof kind === 'string' && typeof message === 'string' ? { kind, message } : null;
}

// A project id is checked by the server's pattern before it reaches a URL; the segment is still encoded.
const PROJECT_ID = /^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$/;
export function isProjectId(id: string): boolean {
  return PROJECT_ID.test(id);
}
function projectPath(id: string, tail = ''): string {
  if (!isProjectId(id)) throw new Error('not a project id');
  return `/api/projects/${encodeURIComponent(id)}${tail}`;
}

export const api = {
  keys: () => request<KeysView>('GET', '/api/keys'),
  saveKey: (name: KeyName, value: string) =>
    request<KeysView>('PUT', `/api/keys/${encodeURIComponent(name)}`, { value }),
  removeKey: (name: KeyName) => request<KeysView>('DELETE', `/api/keys/${encodeURIComponent(name)}`),
  projects: () => request<ProjectList>('GET', '/api/projects'),
  createProject: (name: string) => request<CreatedProject>('POST', '/api/projects', { name }),
  project: (id: string) => request<ProjectDetail>('GET', projectPath(id)),
  script: (id: string) => request<ScriptText>('GET', projectPath(id, '/script')),
  saveScript: (id: string, text: string) => request<{ saved: boolean }>('PUT', projectPath(id, '/script'), { text }),
  checkScript: (id: string, text: string) => request<CheckAnswer>('POST', projectPath(id, '/check'), { text }),
  catalog: () => request<Catalog>('GET', '/api/catalog'),
  beats: (id: string) => request<BeatsDocument>('GET', projectPath(id, '/beats')),
  startJob: (id: string, body: StartBody) => request<CurrentJob>('POST', projectPath(id, '/jobs'), body),
  reveal: (id: string) => request<{ ok: boolean }>('POST', projectPath(id, '/reveal')),
  currentJob: () => request<CurrentJob>('GET', '/api/jobs/current'),
  cancelJob: (run: string) => request<{ cancelling: boolean }>('POST', '/api/jobs/current/cancel', { run }),
  getJobByRun: (run: string) => request<CurrentJob>('GET', `/api/jobs/current?run=${encodeURIComponent(run)}`)
};

export const getCatalog = api.catalog;

/** The audio route's URL; ordinals are zero-padded to NNN.wav (the server takes three to six digits). */
export function audioUrl(projectId: string, ordinal: number): string {
  return projectPath(projectId, `/audio/${String(ordinal).padStart(3, '0')}.wav`);
}

/** The pack zip download URL (same-origin GET navigation; the cookie authenticates it). */
export function packZipUrl(projectId: string): string {
  return projectPath(projectId, '/pack.zip');
}

/** The same-origin stream URL; the job store opens it. */
export const EVENTS_URL = '/api/jobs/current/events';
