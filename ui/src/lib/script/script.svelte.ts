// The script model: the text box content, the saved text, the check result. State comes from the server (save and check
// answers, the detail re-read); nothing is stored in the browser.
import { api } from '../api/client';
import { ApiError, FIXED_MESSAGE, NetworkError } from '../api/errors';
import { LINE_ENDINGS_NOTE, LatestOnly, decodeUpload, normalise, UPLOAD_LIMIT, TOO_LARGE } from './pure';

export const CHECK_DELAY_MS = 800;

export interface ScriptProblem {
  line: number;
  message: string;
}
/** What the last answered check says; `null` means no usable answer (never "no problems"). */
export type CheckView = { ok: true; scenes: number } | { ok: false; problem: ScriptProblem } | null;

export interface ScriptDeps {
  /** True while the job store shows a live job in any project. */
  jobActive: () => boolean;
  /** Re-read the project detail after a save. */
  reread: () => Promise<void>;
}

function shown(error: unknown): string {
  return error instanceof ApiError || error instanceof NetworkError ? error.message : FIXED_MESSAGE;
}

export class ScriptModel {
  text = $state('');
  savedText = $state('');
  loaded = $state(false);
  loadError = $state<string | null>(null);
  /** Plain note when load or upload changed line endings or removed a hidden marker. */
  note = $state<string | null>(null);
  check = $state.raw<CheckView>(null);
  checkError = $state<string | null>(null);
  checking = $state(false);
  saving = $state(false);
  saveError = $state<string | null>(null);
  /** True only after the server confirmed a save of the text that is still in the box. */
  justSaved = $state(false);
  uploadError = $state<string | null>(null);

  #id: string;
  #deps: ScriptDeps;
  #generation = new LatestOnly();
  #timer: ReturnType<typeof setTimeout> | null = null;

  constructor(id: string, deps: ScriptDeps) {
    this.#id = id;
    this.#deps = deps;
  }

  get dirty(): boolean {
    return this.text !== this.savedText;
  }

  /** Save and the beats button grey out while any job holds the slot or a save is in flight. */
  get greyed(): boolean {
    return this.saving || this.#deps.jobActive();
  }

  async load(): Promise<void> {
    try {
      const answer = await api.script(this.#id);
      const clean = normalise(answer.text);
      this.savedText = answer.text; // what the file holds; a CRLF file then shows as an unsaved change
      this.text = clean.text;
      this.note = clean.changed ? LINE_ENDINGS_NOTE : null;
      this.loadError = null;
      this.loaded = true;
      void this.runCheck();
    } catch (error) {
      this.loadError = shown(error);
    }
  }

  /** The text box changed. The check runs after a pause, never per keystroke. */
  edit(next: string): void {
    const clean = normalise(next);
    this.text = clean.text;
    if (clean.changed) this.note = LINE_ENDINGS_NOTE;
    this.justSaved = false;
    this.saveError = null;
    this.#generation.next(); // an answer in flight for older text is now stale
    if (this.#timer !== null) clearTimeout(this.#timer);
    this.#timer = setTimeout(() => void this.runCheck(), CHECK_DELAY_MS);
  }

  async runCheck(): Promise<void> {
    if (this.#timer !== null) {
      clearTimeout(this.#timer);
      this.#timer = null;
    }
    const generation = this.#generation.next();
    this.checking = true;
    try {
      const answer = await api.checkScript(this.#id, this.text);
      if (!this.#generation.isLatest(generation)) return;
      this.check = answer.ok ? { ok: true, scenes: answer.scenes } : this.#firstProblem(answer.problems);
      this.checkError = this.check === null ? FIXED_MESSAGE : null;
    } catch (error) {
      if (!this.#generation.isLatest(generation)) return; // an old failure must not clear a newer result
      this.check = null;
      this.checkError = shown(error);
    } finally {
      if (this.#generation.isLatest(generation)) this.checking = false;
    }
  }

  #firstProblem(problems: ScriptProblem[]): CheckView {
    const first = problems[0];
    return first ? { ok: false, problem: { line: first.line, message: first.message } } : null;
  }

  async save(): Promise<void> {
    if (this.greyed) return;
    const sent = this.text;
    this.saving = true;
    this.saveError = null;
    try {
      await api.saveScript(this.#id, sent);
      this.savedText = sent;
      this.justSaved = this.text === sent;
      if (this.justSaved) this.note = null; // the saved file is now LF-only and marker-free
    } catch (error) {
      this.saveError = shown(error);
      return;
    } finally {
      this.saving = false;
    }
    // The save is confirmed; a failed re-read must not show as a failed save (the page shows its own state).
    try {
      await this.#deps.reread();
    } catch {
      // the detail stays as it was
    }
    void this.runCheck();
  }

  /** A chosen file replaces the box content in the browser only; it is not saved until Save. */
  async upload(file: File): Promise<void> {
    this.uploadError = null;
    if (file.size > UPLOAD_LIMIT) {
      this.uploadError = TOO_LARGE;
      return;
    }
    const decoded = decodeUpload(await file.arrayBuffer());
    if (!decoded.ok) {
      this.uploadError = decoded.message;
      return;
    }
    const clean = normalise(decoded.text);
    this.note = clean.changed ? LINE_ENDINGS_NOTE : null;
    this.edit(clean.text);
  }

  dispose(): void {
    if (this.#timer !== null) clearTimeout(this.#timer);
    this.#timer = null;
    this.#generation.next();
  }
}
