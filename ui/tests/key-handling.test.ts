// Key-handling table (U17). Every row is P0: a key value must leave the page only in its PUT body.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { KeyName } from '../src/lib/api/types';
import { afterPartialSave, KeysModel } from '../src/lib/keys.svelte';

const SECRET = 'sk-test-SECRET-value-123';
const OTHER_SECRET = 'xi-test-OTHER-value-456';
const NAMES = ['GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION', 'VERTEX_AUTHORIZATION_KEY', 'ELEVENLABS_API_KEY', 'OPENROUTER_API_KEY'];
const NON_SECRET = ['GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION'];

interface Seen {
  method: string;
  url: string;
  body: string | null;
}

/** A small stand-in for the key routes: PUT saves, GET and PUT answer the refreshed status. */
function fakeServer(options: { rejectName?: string; echoValue?: boolean } = {}) {
  const store = new Map<string, string>();
  const seen: Seen[] = [];
  const view = () => ({
    path: '/scratch/keys.env',
    keys: Object.fromEntries(
      NAMES.map((name) => [name, store.has(name) ? (NON_SECRET.includes(name) ? { saved: true, value: store.get(name) } : { saved: true }) : { saved: false }])
    ),
    suggested_region: 'europe-west4',
    ignored_environment: []
  });
  const reply = (status: number, body: unknown) => ({ ok: status < 400, status, json: async () => body });
  const fake = vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    const body = typeof init.body === 'string' ? init.body : null;
    seen.push({ method, url, body });
    const name = decodeURIComponent(url.replace('/api/keys/', ''));
    if (method === 'PUT') {
      const value = (JSON.parse(body ?? '{}') as { value: string }).value;
      if (name === options.rejectName) {
        const message = options.echoValue ? `The provider refused ${value}.` : 'The provider refused that value.';
        return reply(400, { error: { kind: 'bad_request', message } });
      }
      store.set(name, value);
    }
    return reply(200, view());
  });
  return { fake, seen, store };
}

function storageSpy() {
  return { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn(), key: vi.fn(), length: 0 };
}

let local: ReturnType<typeof storageSpy>;
let session: ReturnType<typeof storageSpy>;
let consoleSpies: ReturnType<typeof vi.spyOn>[];

beforeEach(() => {
  local = storageSpy();
  session = storageSpy();
  vi.stubGlobal('localStorage', local);
  vi.stubGlobal('sessionStorage', session);
  consoleSpies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((level) => vi.spyOn(console, level).mockImplementation(() => {}));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function loaded(server: ReturnType<typeof fakeServer>) {
  vi.stubGlobal('fetch', server.fake);
  const model = new KeysModel();
  await model.load();
  return model;
}

describe('key handling', () => {
  it('P0: a good save clears each secret field and leaves the project ID and region', async () => {
    const model = await loaded(fakeServer());
    model.fields.VERTEX_AUTHORIZATION_KEY.input = SECRET;
    model.fields.GOOGLE_CLOUD_PROJECT.input = 'my-project';
    model.fields.GOOGLE_CLOUD_LOCATION.input = 'europe-west1';
    model.fields.ELEVENLABS_API_KEY.input = OTHER_SECRET;

    expect((await model.save(model.googleNames())).ok).toBe(true);
    expect((await model.save(['ELEVENLABS_API_KEY'])).ok).toBe(true);

    expect(model.fields.VERTEX_AUTHORIZATION_KEY.input).toBe('');
    expect(model.fields.ELEVENLABS_API_KEY.input).toBe('');
    expect(model.fields.GOOGLE_CLOUD_PROJECT.input).toBe('my-project');
    expect(model.fields.GOOGLE_CLOUD_LOCATION.input).toBe('europe-west1');
    expect(model.fields.VERTEX_AUTHORIZATION_KEY.saved).toBe(true);
  });

  it('P0 key-leak: after a partial save a saved secret is cleared and never asked for or sent again (Google key saved, project ID refused)', async () => {
    const server = fakeServer({ rejectName: 'GOOGLE_CLOUD_PROJECT' });
    const model = await loaded(server);
    const asked: KeyName[] = ['VERTEX_AUTHORIZATION_KEY', 'GOOGLE_CLOUD_PROJECT'];
    model.fields.VERTEX_AUTHORIZATION_KEY.input = SECRET;
    model.fields.GOOGLE_CLOUD_PROJECT.input = 'my-project';

    const first = await model.save(asked);
    const rule = afterPartialSave(asked, first.saved);

    expect(first.ok).toBe(false);
    expect(rule.ask).toEqual(['GOOGLE_CLOUD_PROJECT']);
    expect(rule.clear).toEqual(['VERTEX_AUTHORIZATION_KEY']);
    expect(model.fields.VERTEX_AUTHORIZATION_KEY.input).toBe('');

    await model.save(rule.ask);
    const sent = server.seen.filter((call) => call.method === 'PUT' && call.url === '/api/keys/VERTEX_AUTHORIZATION_KEY');
    expect(sent).toHaveLength(1);
  });

  it('P0: a failed save keeps the typed value and the shown message does not contain it', async () => {
    const model = await loaded(fakeServer({ rejectName: 'ELEVENLABS_API_KEY', echoValue: true }));
    model.fields.ELEVENLABS_API_KEY.input = SECRET;

    const result = await model.save(['ELEVENLABS_API_KEY']);

    expect(result.ok).toBe(false);
    expect(model.fields.ELEVENLABS_API_KEY.input).toBe(SECRET);
    expect(model.error?.name).toBe('ELEVENLABS_API_KEY');
    expect(model.error?.message).not.toContain(SECRET);
    expect(model.error?.message.length).toBeGreaterThan(0);
  });

  it('P0: the value appears only in its PUT body, and nothing is written to storage or the console', async () => {
    const server = fakeServer();
    const model = await loaded(server);
    model.fields.VERTEX_AUTHORIZATION_KEY.input = SECRET;
    model.fields.GOOGLE_CLOUD_PROJECT.input = 'my-project';
    model.fields.OPENROUTER_API_KEY.input = OTHER_SECRET;
    await model.save(model.googleNames());
    await model.save(['OPENROUTER_API_KEY']);
    await model.remove('OPENROUTER_API_KEY');

    for (const call of server.seen) {
      expect(call.url).not.toContain(SECRET);
      expect(call.url).not.toContain(OTHER_SECRET);
      const carries = (call.body ?? '').includes(SECRET) || (call.body ?? '').includes(OTHER_SECRET);
      expect(carries).toBe(call.method === 'PUT' && /VERTEX_AUTHORIZATION_KEY|OPENROUTER_API_KEY/.test(call.url));
    }
    expect(server.seen.find((call) => call.method === 'DELETE')?.body).toBeNull();
    expect(server.seen.some((call) => call.url === '/api/keys/VERTEX_AUTHORIZATION_KEY' && call.body === JSON.stringify({ value: SECRET }))).toBe(true);
    for (const spy of [...Object.values(local), ...Object.values(session)]) {
      if (typeof spy === 'function') expect(spy).not.toHaveBeenCalled();
    }
    for (const spy of consoleSpies) expect(spy).not.toHaveBeenCalled();
    expect(JSON.stringify(model.fields)).not.toContain(SECRET);
  });
});
