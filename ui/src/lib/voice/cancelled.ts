// The cancelled and partly voiced states (pure): which scenes the page names, and which offers show.
// APPROVED (spec "Waiting and errors"): "Stopped. Scenes 1 and 2 are voiced and kept. Scenes 3 to 6 were not."
// PROPOSED (owner gate): the single-scene and non-contiguous forms, "nothing voiced", "all voiced", the quota note.
import type { AudioSettings, ProjectDetail } from '../api/types';
import type { VoiceMode } from './flow';

export const CANCELLED_WORDS = {
  quotaNote: 'The scene being voiced at the moment you stopped may still have used quota.', // PROPOSED
  rest: 'Voice the rest', // approved
  restart: 'Start again', // approved
  back: 'Back'
} as const;

/** "Scene 3", "Scenes 1 and 2", "Scenes 3 to 6" (three or more in a row), "Scenes 1, 3 and 4" (otherwise). */
function name(ordinals: readonly number[]): string {
  const last = ordinals[ordinals.length - 1];
  if (ordinals.length === 1) return `Scene ${last}`;
  const run = ordinals.length > 2 && ordinals.every((n, i) => i === 0 || n === ordinals[i - 1] + 1);
  if (run) return `Scenes ${ordinals[0]} to ${last}`;
  return `Scenes ${ordinals.slice(0, -1).join(', ')} and ${last}`;
}

export function cancelledText(voiced: readonly number[], unvoiced: readonly number[]): string {
  if (voiced.length === 0) return 'Stopped. No scene is voiced yet.';
  const kept = `${name(voiced)} ${voiced.length === 1 ? 'is' : 'are'} voiced and kept.`;
  if (unvoiced.length === 0) return `Stopped. ${kept}`;
  return `Stopped. ${kept} ${name(unvoiced)} ${unvoiced.length === 1 ? 'was' : 'were'} not.`;
}

/** The scene numbers voiced and not voiced, in script order, from the detail read after the run. */
export function sceneSets(detail: ProjectDetail): { voiced: number[]; unvoiced: number[] } {
  const voiced = new Set((detail.audio?.scenes ?? []).filter((entry) => entry.voiced).map((entry) => entry.ordinal));
  const ordinals = detail.script.scenes.map((entry) => entry.ordinal);
  return { voiced: ordinals.filter((n) => voiced.has(n)), unvoiced: ordinals.filter((n) => !voiced.has(n)) };
}

/** The offers the server's `can` allows: the rest (recorded settings), then a fresh start. Never derived by the page. */
export function offeredModes(can: ProjectDetail['can']): VoiceMode[] {
  return (['rest', 'restart'] as const).filter((mode) => can?.synth?.[mode] === true);
}

/** The model of a run seen on resume or at its end: the record's, else the fallback. */
export function runModelFor(settings: AudioSettings | null | undefined, fallback: string): string {
  return settings?.model || fallback;
}
