// Error types and the stale-link handler registration (U6).

export const FIXED_MESSAGE = 'SceneVoice could not finish. Try again.';

/** A server answer of the form {"error": {kind, message}}; `message` is shown as the server wrote it. */
export class ApiError extends Error {
  readonly status: number;
  readonly kind: string;
  constructor(status: number, kind: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
  }
}

/** `fetch` itself threw: the server is not reachable. */
export class NetworkError extends Error {
  constructor() {
    super('SceneVoice is not answering.');
    this.name = 'NetworkError';
  }
}

let staleHandler: (() => void) | null = null;

/** The connection module registers what to do when the server says this link is from an earlier run. */
export function onStaleLink(handler: (() => void) | null): void {
  staleHandler = handler;
}

export function notifyStaleLink(): void {
  staleHandler?.();
}
