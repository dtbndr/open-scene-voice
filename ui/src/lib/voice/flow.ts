// The voice start flow as explicit phases, mirroring the beats flow. `transition` is pure: a paid request is posted only
// from the confirmation's own confirm; the popup callback, "Try again", a rejected snapshot and a resumed run never reach
// `starting`, they go back to a fresh read and a fresh confirmation.
import { snapshotFor } from '../api/confirm';
import { tryAgainMode } from './failure';
import type { SceneStatus } from '../jobs/reduce';
import { KEY_NAMES, type Catalog, type FailureKind, type JobMode, type KeyName, type ProjectDetail } from '../api/types';

export interface VoiceFailure {
  kind: FailureKind;
  status: number | null;
  message: string;
  /** The scene the last `fail` event names (the server always sends it; align uses it for "Scene N: "). */
  scene?: number | null;
}

export type VoicePhase =
  | { phase: 'choose' }
  | { phase: 'popup' }
  | { phase: 'confirming' }
  | { phase: 'starting' }
  | { phase: 'running' }
  | { phase: 'failed'; failure: VoiceFailure }
  | { phase: 'cancelled' }
  | { phase: 'showing' };

export type VoiceAction =
  | { type: 'press'; keysMissing: boolean }
  | { type: 'popupDone' }
  | { type: 'popupCancel' }
  | { type: 'dismiss' }
  | { type: 'resumed' }
  | { type: 'confirm' }
  | { type: 'rejected'; reason: 'changed' | 'not_allowed' | 'busy' }
  | { type: 'started' }
  | { type: 'ended'; outcome: 'done' | 'cancelled' | 'failed'; failure?: VoiceFailure }
  | { type: 'tryAgain' }
  | { type: 'back' }
  | { type: 'redo' };

const CHOOSE: VoicePhase = { phase: 'choose' };
const CONFIRMING: VoicePhase = { phase: 'confirming' };
const OTHER: VoiceFailure = { kind: 'other', status: null, message: '' };

/** State and action in, state out. An action that does not apply leaves the state unchanged. */
export function transition(state: VoicePhase, action: VoiceAction): VoicePhase {
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
      const failure = action.failure ?? OTHER;
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

// ---- Choice screen (slice D) ----------------------------------------------------------------------------------------

export type VoiceMode = JobMode;
/** Where the voice page opens: nothing voiced yet, some scenes voiced, or every scene voiced. */
export type VoiceEntry = 'fresh' | 'partly' | 'full';

// Approved wording (owner, 2026-11-21): every new string of the choice screen lives here. The radio labels are the approved long forms.
export const MODEL_LABELS: Record<string, string> = {
  'gemini-3.8-flash-tts': 'Gemini, standard quality (Google Cloud key)',
  'gemini-3.8-flash-lite-tts': 'Gemini, lighter and quicker (Google Cloud key)',
  eleven_flash_v2_5: 'ElevenLabs, quick (ElevenLabs key)',
  eleven_v4: 'ElevenLabs, highest quality (ElevenLabs key)'
};
export const VOICE_WORDS = {
  title: 'Voice',
  provider: 'Provider / model',
  voice: 'Voice',
  voiceId: 'Voice ID',
  voiceIdHint: 'Paste the voice ID from your ElevenLabs account.',
  language: 'Language',
  style: 'Delivery style',
  stylePlaceholder: 'e.g. "warm, unhurried" (optional)',
  next: 'Next: Generate',
  busy: 'SceneVoice is busy with another job. This button works again when it finishes.',
  busyForeign: 'SceneVoice is busy with another job. Voicing is available again when it finishes.', // approved: the foreign-job view
  unavailable: 'Voicing is not available for this project right now.',
  modeRest: 'Voice the rest',
  modeRestart: 'Start again',
  restNote: 'The rest uses the settings of the scenes already voiced.',
  fullyVoiced: 'Every scene is voiced.',
  toReview: 'Review the scenes',
  startAgain: 'Start again',
  back: 'Back'
} as const;

// Approved wording (owner, 2026-11-21): the confirmation (spec text, short model names) and the running view.
export const SHORT_LABELS: Record<string, string> = {
  'gemini-3.8-flash-tts': 'Gemini standard',
  'gemini-3.8-flash-lite-tts': 'Gemini lighter',
  eleven_flash_v2_5: 'ElevenLabs quick',
  eleven_v4: 'ElevenLabs highest quality'
};
export const CONFIRM_WORDS = {
  title: 'Ready to voice this script?',
  quota: 'This uses your provider quota. You can cancel while it runs, but scenes already voiced have already used quota.',
  back: 'Back'
} as const;
export const PROGRESS_WORDS = {
  starting: 'Starting...',
  title: 'Generating',
  cancel: 'Cancel',
  stopping: 'Stopping...',
  keepOpen: 'Keep the Terminal window open. This can take a few minutes.',
  cancelNote: 'Scenes already voiced have already used quota.',
  done: 'done',
  voicing: 'voicing...',
  waiting: 'waiting',
  play: 'Play scene', // approved: the row play button, for a voiced scene
  failed: 'Voicing did not finish.'
} as const;

export function confirmSummary(scenes: number, characters: number, modelId: string | null): string {
  const noun = scenes === 1 ? 'scene' : 'scenes';
  const label = SHORT_LABELS[modelId ?? ''] ?? modelId ?? '';
  return `${scenes} ${noun}, ${characters.toLocaleString('en-GB')} characters, ${label}.`;
}

export function voiceButton(scenes: number): string {
  return `Voice ${scenes} ${scenes === 1 ? 'scene' : 'scenes'}`;
}

/** The scene numbers a synth job covers, from the detail read when it started (the unvoiced ones for the rest). */
export function pendingOrdinals(detail: ProjectDetail, mode: VoiceMode | null): number[] {
  const voiced = new Set((detail.audio?.scenes ?? []).filter((entry) => entry.voiced).map((entry) => entry.ordinal));
  return detail.script.scenes.map((entry) => entry.ordinal).filter((ordinal) => mode !== 'rest' || !voiced.has(ordinal));
}

export type RowStatus = 'done' | 'voicing' | 'waiting';

/** One row per scene number (the pending ones and any the stream reported), in order, keyed by that number. */
export function progressRows(pending: readonly number[], seen: Readonly<Record<number, SceneStatus>>): { ordinal: number; status: RowStatus }[] {
  const ordinals = [...new Set([...pending, ...Object.keys(seen).map(Number)])].sort((a, b) => a - b);
  return ordinals.map((ordinal) => {
    const status = seen[ordinal];
    return { ordinal, status: status === 'done' || status === 'kept' ? 'done' : status === 'started' ? 'voicing' : 'waiting' };
  });
}

/** The cost line shared by the choice screen and the confirmation: "This job: N scenes, M characters. ..." */
export function costLine(scenes: number, characters: number): string {
  const noun = scenes === 1 ? 'scene' : 'scenes';
  return `This job: ${scenes} ${noun}, ${characters.toLocaleString('en-GB')} characters. Voicing uses your provider quota.`;
}

export function entryOf(detail: ProjectDetail): VoiceEntry {
  const voiced = (detail.audio?.scenes ?? []).filter((entry) => entry.voiced).length;
  const planned = detail.script.scenes.length;
  if (voiced === 0) return 'fresh';
  return voiced >= planned ? 'full' : 'partly';
}

/** The synth mode a press starts, or null when the server's `can` does not allow it. */
export function chooseKind(can: ProjectDetail['can'], mode: VoiceMode): { kind: 'synth'; mode: VoiceMode } | null {
  return can?.synth?.[mode] === true ? { kind: 'synth', mode } : null;
}

/** The mode a page opens on: a fresh project voices all; a partly voiced one offers the rest first. */
export function defaultMode(entry: VoiceEntry, can: ProjectDetail['can']): VoiceMode {
  if (entry === 'fresh') return 'all';
  return can?.synth?.rest === true ? 'rest' : 'restart';
}

/** The mode a press starts: the retry rule when retrying, and a default when the held mode is not allowed (a partial run after the key popup). */
export function settleMode(detail: ProjectDetail, mode: VoiceMode, retry: boolean): VoiceMode {
  const next = retry ? tryAgainMode(detail.can, mode) : mode;
  return chooseKind(detail.can, next) === null ? defaultMode(entryOf(detail), detail.can) : next;
}

/** The radios, in the catalog's order: [model id, label]; an unknown model shows its id. */
export function radioModels(catalog: Catalog): { id: string; label: string }[] {
  return Object.values(catalog.providers).flatMap((spec) =>
    spec.models.map((id) => ({ id, label: MODEL_LABELS[id] ?? id }))
  );
}

export function providerOf(catalog: Catalog, modelId: string): Catalog['providers'][string] | null {
  return Object.values(catalog.providers).find((spec) => spec.models.includes(modelId)) ?? null;
}

/** The key names a provider needs (names the UI does not know are dropped). */
export function neededKeys(spec: Catalog['providers'][string] | null): KeyName[] {
  return (spec?.env_names ?? []).filter((name): name is KeyName => (KEY_NAMES as readonly string[]).includes(name));
}

/** Scene and character counts for the cost line, from the same `snapshotFor` the confirmation uses. The voice here is a
 * placeholder that only satisfies the builder; it is never sent. Null when the snapshot cannot be built. */
export function costFor(detail: ProjectDetail, mode: VoiceMode, modelId: string): { scenes: number; characters: number } | null {
  try {
    const shot = snapshotFor('synth', mode, detail, undefined, modelId, { voice: 'counts only' });
    return { scenes: shot.scenes ?? 0, characters: shot.characters ?? 0 };
  } catch {
    return null;
  }
}
