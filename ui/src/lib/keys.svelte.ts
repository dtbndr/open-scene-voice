// The Keys model (U12). `save` is the only place a key value leaves the page: one PUT body per name.
import { api } from './api/client';
import { ApiError, FIXED_MESSAGE, NetworkError } from './api/errors';
import { KEY_NAMES, NON_SECRET_NAMES } from './api/types';
import type { KeyName, KeysView } from './api/types';

/** The order a multi-field save sends its PUTs: key, project ID, region, then the single-key providers. */
export const SEND_ORDER: readonly KeyName[] = [
  'VERTEX_AUTHORIZATION_KEY',
  'GOOGLE_CLOUD_PROJECT',
  'GOOGLE_CLOUD_LOCATION',
  'ELEVENLABS_API_KEY',
  'OPENROUTER_API_KEY'
];

export class KeyField {
  readonly name: KeyName;
  readonly secret: boolean;
  /** What the server says is saved; a secret's value is never known to the page. */
  saved = $state(false);
  savedValue = $state<string | null>(null);
  /** The typed text: the one place a value lives before its PUT. */
  input = $state('');
  constructor(name: KeyName) {
    this.name = name;
    this.secret = !NON_SECRET_NAMES.includes(name);
  }
}

export interface SaveFailure {
  name: KeyName;
  message: string;
}

export interface SaveResult {
  ok: boolean;
  /** Names saved by this call, in the order sent. */
  saved: KeyName[];
  failed: SaveFailure | null;
}

/** Names in `needed` that the status says are not saved (the popup asks for exactly these). */
export function missingKeys(needed: readonly KeyName[], status: KeysView): KeyName[] {
  return needed.filter((name) => !status.keys[name]?.saved);
}

/** What a popup does after a save that stopped partway (item 15): ask and send only the names not yet saved, and clear
 * the typed text of every secret that was saved, so a saved secret is never held, asked for or sent again. */
export function afterPartialSave(asked: readonly KeyName[], saved: readonly KeyName[]): { ask: KeyName[]; clear: KeyName[] } {
  return {
    ask: asked.filter((name) => !saved.includes(name)),
    clear: asked.filter((name) => saved.includes(name) && !NON_SECRET_NAMES.includes(name))
  };
}

function shownMessage(error: unknown, typed: string): string {
  const message =
    error instanceof ApiError || error instanceof NetworkError ? error.message : FIXED_MESSAGE;
  // Defensive: a message that echoes what was typed is replaced, so the value never reaches the DOM.
  return typed !== '' && message.includes(typed) ? FIXED_MESSAGE : message;
}

export class KeysModel {
  fields = Object.fromEntries(KEY_NAMES.map((name) => [name, new KeyField(name)])) as Record<KeyName, KeyField>;
  loaded = $state(false);
  loadError = $state<string | null>(null);
  suggestedRegion = $state('');
  ignored = $state<string[]>([]);
  busy = $state(false);
  /** The last failed save, shown by the row it belongs to. Cleared when a new save starts. */
  error = $state<SaveFailure | null>(null);

  async load(): Promise<void> {
    try {
      this.adopt(await api.keys());
      this.loadError = null;
    } catch (error) {
      this.loadError = shownMessage(error, '');
    }
  }

  /** Take the server's status. Typed secrets and unsaved typed text are left alone. */
  private adopt(view: KeysView): void {
    this.suggestedRegion = view.suggested_region;
    this.ignored = view.ignored_environment;
    for (const name of KEY_NAMES) {
      const field = this.fields[name];
      const status = view.keys[name];
      field.saved = status?.saved === true;
      if (!field.secret) {
        const before = field.savedValue;
        field.savedValue = field.saved ? (status?.value ?? '') : null;
        // A value the creator is still editing is not overwritten by another row's refreshed status.
        const untouched = field.input === '' || field.input === before || field.input === this.suggestedRegion;
        if (field.saved && untouched) field.input = field.savedValue ?? '';      }
    }
    const region = this.fields.GOOGLE_CLOUD_LOCATION;
    if (!region.saved && region.input === '') region.input = this.suggestedRegion;
    this.loaded = true;
  }

  /** Names a Google row Save would send: typed key and project ID, plus the region once it matters. */
  googleNames(): KeyName[] {
    const [key, project, region] = SEND_ORDER.slice(0, 3).map((name) => this.fields[name]);
    const names: KeyName[] = [];
    if (key.input.trim() !== '') names.push(key.name);
    if (project.input.trim() !== '' && project.input !== project.savedValue) names.push(project.name);
    const typed = region.input.trim() !== '' && region.input !== region.savedValue;
    const edited = region.input !== this.suggestedRegion;
    if (typed && (names.length > 0 || edited)) names.push(region.name);
    return names;
  }

  /** One PUT per filled name in send order; stops at the first failure and leaves earlier saves in place. */
  async save(names: readonly KeyName[]): Promise<SaveResult> {
    this.error = null;
    this.busy = true;
    const saved: KeyName[] = [];
    try {
      for (const name of SEND_ORDER.filter((candidate) => names.includes(candidate))) {
        const field = this.fields[name];
        const value = field.input.trim();
        if (value === '') continue;
        try {
          const view = await api.saveKey(name, value);
          if (field.secret) field.input = '';
          this.adopt(view);
          saved.push(name);
        } catch (error) {
          const failure = { name, message: shownMessage(error, value) };
          this.error = failure;
          return { ok: false, saved, failed: failure };
        }
      }
      return { ok: true, saved, failed: null };
    } finally {
      this.busy = false;
    }
  }

  async remove(name: KeyName): Promise<SaveResult> {
    this.error = null;
    this.busy = true;
    try {
      this.adopt(await api.removeKey(name));
      return { ok: true, saved: [], failed: null };
    } catch (error) {
      const failure = { name, message: shownMessage(error, '') };
      this.error = failure;
      return { ok: false, saved: [], failed: failure };
    } finally {
      this.busy = false;
    }
  }
}
