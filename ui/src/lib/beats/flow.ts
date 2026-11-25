// The beats start flow as explicit phases (items 10 to 13). `transition` is pure: the one rule it carries is that a paid
// request is posted only from the confirmation's own confirm; everything else (popup callback, "Try again", a rejected
// snapshot) goes back to re-reading the detail and opening a fresh confirmation, never to `starting`.
import { FIXED_MESSAGE } from '../api/errors';
import type { FailureKind, JobKind, ProjectDetail } from '../api/types';

export interface BeatsFailure {
  kind: FailureKind;
  status: number | null;
  message: string;
}

export type BeatsPhase =
  | { phase: 'choose' }
  | { phase: 'popup' }
  | { phase: 'confirming' }
  | { phase: 'starting' }
  | { phase: 'running' }
  | { phase: 'failed'; failure: BeatsFailure }
  | { phase: 'cancelled' }
  | { phase: 'showing' };

export type BeatsAction =
  | { type: 'press'; keysMissing: boolean }
  | { type: 'popupDone' }
  | { type: 'popupCancel' }
  | { type: 'dismiss' }
  | { type: 'resumed' }
  | { type: 'confirm' }
  | { type: 'rejected'; reason: 'changed' | 'not_allowed' | 'busy' }
  | { type: 'started' }
  | { type: 'ended'; outcome: 'done' | 'cancelled' | 'failed'; failure?: BeatsFailure }
  | { type: 'tryAgain' }
  | { type: 'back' }
  | { type: 'redo' };

const CHOOSE: BeatsPhase = { phase: 'choose' };
const CONFIRMING: BeatsPhase = { phase: 'confirming' };

/** State and action in, state out. An action that does not apply leaves the state unchanged. */
export function transition(state: BeatsPhase, action: BeatsAction): BeatsPhase {
  switch (action.type) {
    case 'press':
      if (state.phase !== 'choose') return state;
      return action.keysMissing ? { phase: 'popup' } : CONFIRMING;
    case 'popupDone':
      return state.phase === 'popup' ? CONFIRMING : state;
    case 'popupCancel':
      return state.phase === 'popup' ? CHOOSE : state;
    case 'dismiss':
      return state.phase === 'confirming' ? CHOOSE : state;
    case 'resumed':
      return state.phase === 'choose' ? { phase: 'running' } : state;
    case 'confirm':
      return state.phase === 'confirming' ? { phase: 'starting' } : state;
    case 'rejected':
      return state.phase === 'starting' ? CHOOSE : state;
    case 'started':
      return state.phase === 'starting' ? { phase: 'running' } : state;
    case 'ended': {
      if (state.phase !== 'running') return state;
      if (action.outcome === 'done') return { phase: 'showing' };
      if (action.outcome === 'cancelled') return { phase: 'cancelled' };
      const failure = action.failure ?? { kind: 'other' as const, status: null, message: FIXED_MESSAGE };
      return failure.kind === 'missing_key' ? { phase: 'popup' } : { phase: 'failed', failure };
    }
    case 'tryAgain':
      return state.phase === 'failed' ? CONFIRMING : state;
    case 'back':
      return state.phase === 'failed' || state.phase === 'cancelled' ? CHOOSE : state;
    case 'redo':
      return state.phase === 'showing' ? CHOOSE : state;
  }
}

/** The job kind comes from the detail's `can` flags, never from `beats.state` (item 8). */
export function chooseKind(can: ProjectDetail['can']): Extract<JobKind, 'beats' | 'beats-redo'> | null {
  if (can?.beats === true) return 'beats';
  if (can?.beats_redo === true) return 'beats-redo';
  return null;
}

export type FailureButton = 'tryAgain' | 'back' | 'checkKey';

export interface FailureWording {
  text: string;
  /** Shown above `text` as a heading when the CLI's own text follows (invalid_input). */
  heading?: string;
  buttons: FailureButton[];
}

const WORDS = {
  badKey: 'OpenRouter did not accept your key. Check that you pasted all of it.',
  noCredit: 'Your OpenRouter account has no credit left. Add credit there, then try again.',
  tooMany: 'OpenRouter says there have been too many requests, or your allowance is used up. Wait a little, then try again.',
  down: 'OpenRouter had a problem. Try again in a minute.',
  connection:
    'The request failed or timed out, and may still have been charged. Check your internet connection, then try again in a minute.',
  refused: 'OpenRouter refused the request. Check the model name, then try again.',
  unusable:
    'OpenRouter answered, but no beats could be made from the reply. It may have been held back, empty or unreadable. Try again, or choose another model.',
  generic:
    'SceneVoice could not finish planning beats. If an answer came back it may have been cut off or incomplete. Try again, or choose another model.',
  invalidHeading: 'SceneVoice could not plan beats for this script.',
  missingKey: 'This needs your OpenRouter key.'
};

/** Kind and status in, wording and buttons out. The message is read only for `other` with no status (a hook's own text)
 * and `invalid_input` (the CLI's text); nothing else looks at it. */
export function failureWording(failure: BeatsFailure): FailureWording {
  const { kind, status, message } = failure;
  switch (kind) {
    case 'missing_key':
      return { text: WORDS.missingKey, buttons: ['tryAgain', 'back'] };
    case 'bad_key':
      return { text: WORDS.badKey, buttons: ['checkKey', 'back'] };
    case 'quota':
      return { text: status === 402 ? WORDS.noCredit : WORDS.tooMany, buttons: ['tryAgain'] };
    case 'provider_down':
      return { text: status !== null && status >= 500 ? WORDS.down : WORDS.connection, buttons: ['tryAgain'] };
    case 'invalid_input':
      return { heading: WORDS.invalidHeading, text: message, buttons: ['back'] };
    default:
      if (status !== null && status >= 400 && status < 500) return { text: WORDS.refused, buttons: ['back'] };
      if (status === 200) return { text: WORDS.unusable, buttons: ['tryAgain', 'back'] };
      if (message !== FIXED_MESSAGE && message !== '') return { text: message, buttons: ['tryAgain', 'back'] };
      return { text: WORDS.generic, buttons: ['tryAgain', 'back'] };
  }
}

export const CANCELLED_WORDS = 'Stopped. A cancelled request may still have been charged.';
export const INVALID_BEATS_WORDS = 'The saved beats could not be read, so none are shown.';
