// The connection watcher (U10): one poll every 5 s while the tab is visible and no stream is open.
// Two thrown fetches in a row mean the server stopped; a 401 stale_link means this page is from an earlier run.
import { ApiError, onStaleLink } from '../api/errors';

export type ConnectionState = 'ok' | 'stopped' | 'earlier';

export interface ConnectionOptions {
  /** One `GET /api/jobs/current` (it refreshes the job store); throws ApiError on an HTTP error, anything else if unreachable. */
  poll: () => Promise<unknown>;
  streamOpen: () => boolean;
  intervalMs?: number;
}

export class Connection {
  state = $state<ConnectionState>('ok');

  #poll: () => Promise<unknown>;
  #streamOpen: () => boolean;
  #intervalMs: number;
  #failures = 0;
  #timer: ReturnType<typeof setInterval> | null = null;
  #busy = false;
  #started = false;

  constructor(options: ConnectionOptions) {
    this.#poll = options.poll;
    this.#streamOpen = options.streamOpen;
    this.#intervalMs = options.intervalMs ?? 5000;
  }

  start(): void {
    if (this.#started) return;
    this.#started = true;
    onStaleLink(() => this.#earlier());
    document.addEventListener('visibilitychange', this.#visibility);
    this.#visibility();
  }

  stop(): void {
    this.#started = false;
    onStaleLink(null);
    document.removeEventListener('visibilitychange', this.#visibility);
    this.#clear();
  }

  #visibility = (): void => {
    this.#clear();
    if (document.visibilityState !== 'visible' || this.state === 'earlier') return;
    void this.check();
    this.#timer = setInterval(() => {
      if (!this.#streamOpen()) void this.check();
    }, this.#intervalMs);
  };

  #clear(): void {
    if (this.#timer !== null) clearInterval(this.#timer);
    this.#timer = null;
  }

  #earlier(): void {
    this.state = 'earlier';
    this.#clear();
  }

  /** One poll. An HTTP answer of any kind resets the failure count; a thrown fetch counts one. */
  async check(): Promise<void> {
    if (this.#busy) return;
    this.#busy = true;
    try {
      await this.#poll();
      this.#failures = 0;
      if (this.state === 'stopped') this.state = 'ok';
    } catch (error) {
      if (error instanceof ApiError) {
        this.#failures = 0;
        if (error.status === 401 && error.kind === 'stale_link') this.#earlier();
        else if (this.state === 'stopped') this.state = 'ok';
      } else {
        this.#failures += 1;
        if (this.#failures >= 2 && this.state === 'ok') this.state = 'stopped';
      }
    } finally {
      this.#busy = false;
    }
  }
}
