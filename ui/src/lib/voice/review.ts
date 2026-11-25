// The review screen's pure rules: the scene notes, the Redo state, Prev and Next, and the redo wording.
// Wording approved by the owner 2026-11-21 (WS47); "Redo this scene" and the replace sentence come from the spec.
import type { AudioScene, AudioSettings, ProjectDetail } from '../api/types';
import { SHORT_LABELS } from './flow';

export const REVIEW_WORDS = {
  title: 'Review',
  previous: 'Previous scene',
  next: 'Next scene',
  redo: 'Redo this scene', // approved
  nextPack: 'Next: Pack', // approved
  notVoiced: 'This scene is not voiced yet.',
  wavChanged: 'The audio file for this scene is not the one SceneVoice made.',
  textChanged: 'The text of this scene has changed since it was voiced.',
  busy: 'SceneVoice is busy with another job. Redo works again when it finishes.',
  confirmTitle: 'Redo this scene?',
  confirmQuota: 'This uses your provider quota for this one scene.',
  confirm: 'Redo scene',
  back: 'Back',
  stopped: 'Stopped. The scene being voiced at the moment you stopped may still have used quota.',
  checkDetails: 'Check my details'
} as const;

/** "This replaces the current audio for scene 2." (approved). */
export function replaceLine(ordinal: number): string {
  return `This replaces the current audio for scene ${ordinal}.`;
}

/** "Voice: Leda, Gemini standard" from the recorded settings; a part the record lacks is left out. */
export function settingsLine(settings: AudioSettings | null | undefined): string {
  const parts = [settings?.voice, settings?.model ? (SHORT_LABELS[settings.model] ?? settings.model) : null].filter(Boolean);
  return `Voice: ${parts.join(', ')}`;
}

/** A plain note only for an explicit false; null (unvoiced or unrecorded) never shows one and never hides the scene. */
export function sceneNotes(entry: Pick<AudioScene, 'wav_matches_record' | 'text_matches'> | undefined): string[] {
  const notes: string[] = [];
  if (entry?.wav_matches_record === false) notes.push(REVIEW_WORDS.wavChanged);
  if (entry?.text_matches === false) notes.push(REVIEW_WORDS.textChanged);
  return notes;
}

export type RedoState = 'hidden' | 'busy' | 'ready';

/** Redo follows the server's `can`; another job running greys it. The page never derives availability. */
export function redoState(can: ProjectDetail['can'], foreignBusy: boolean): RedoState {
  if (can?.synth_scene !== true) return 'hidden';
  return foreignBusy ? 'busy' : 'ready';
}

/** The scene after (+1) or before (-1) the current one in the script's own numbers; null at either end. */
export function stepScene(ordinals: readonly number[], current: number, step: 1 | -1): number | null {
  return ordinals[ordinals.indexOf(current) + step] ?? null;
}
