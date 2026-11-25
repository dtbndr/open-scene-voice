// Pack failure views (pure). The OpenRouter kind/status mapping is copied by value from beats/flow.ts `failureWording`;
// nothing beats-specific is imported. Approved wording (owner signed off 2026-11-23), see words.ts.
import { FIXED_MESSAGE } from '../api/errors';
import type { VoiceFailure } from '../voice/flow';
import { PACK_WORDS } from './words';

export type PackButton = 'tryAgain' | 'checkDetails' | 'back';
export interface AlignFailureShown {
  popup: false;
  heading: string;
  text: string;
  footer: string;
  buttons: PackButton[];
}
/** A missing key is not a failure screen: the controller opens the key popup and retries from a fresh read. */
export type AlignFailureView = { popup: true } | AlignFailureShown;
export interface PackFailureView {
  heading: string;
  text: string;
  buttons: PackButton[];
}

const usable = (message: string): boolean => message !== '' && message !== FIXED_MESSAGE;

/** "Scene N: " before the reason, unless the text already starts with it (any case). */
function withScene(text: string, scene: number | null | undefined): string {
  if (scene === null || scene === undefined) return text;
  return text.toLowerCase().startsWith(`scene ${scene}`) ? text : `Scene ${scene}: ${text}`;
}

export function alignFailureView(failure: VoiceFailure): AlignFailureView {
  const { kind, status, message, scene } = failure;
  if (kind === 'missing_key') return { popup: true };
  let text: string;
  let buttons: PackButton[] = ['tryAgain', 'back'];
  switch (kind) {
    case 'bad_key':
      text = PACK_WORDS.badKey;
      buttons = ['checkDetails', 'tryAgain', 'back'];
      break;
    case 'quota':
      text = status === 402 ? PACK_WORDS.noCredit : PACK_WORDS.tooMany;
      break;
    case 'provider_down':
      text = status !== null && status >= 500 ? PACK_WORDS.down : PACK_WORDS.connection;
      break;
    default: // invalid_input and other show the CLI text
      text = usable(message) ? message : PACK_WORDS.generic;
  }
  return { popup: false, heading: PACK_WORDS.alignHeading, text: withScene(text, scene), footer: PACK_WORDS.footer, buttons };
}

export function packFailureView(failure: VoiceFailure): PackFailureView {
  const text = usable(failure.message) ? failure.message : PACK_WORDS.generic;
  return { heading: PACK_WORDS.packHeading, text, buttons: ['tryAgain', 'back'] };
}
