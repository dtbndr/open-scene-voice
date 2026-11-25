// Every new Pack string in one place. APPROVED (owner signed off 2026-11-23).
// Spec text already owner-reviewed is marked "spec". The label "Line markers" is shown once by the component; the
// status strings below carry no prefix (so "Line markers" + "Up to date"), never "Line markers: Up to date" twice.

/** More scenes than this are counted ("4 scenes") instead of listed ("scenes 2, 3 and 5"). */
export const LIST_LIMIT = 3;

export const PACK_WORDS = {
  markersLabel: 'Line markers', // spec
  updateButton: 'Update line markers', // spec
  statusNone: 'Not made yet',
  statusFresh: 'Up to date', // spec
  statusUnreadable: 'Could not be read. Update line markers to make them again.',
  updating: 'Updating line markers...',
  packing: 'Packing...',
  cancel: 'Cancel',
  listening: 'listening',
  waiting: 'waiting',
  done: 'done',
  title: 'Pack for DaVinci Resolve', // spec
  markersIntro: 'Markers in the timeline:', // spec
  sceneMarkers: 'Scene markers', // spec
  alwaysIncluded: 'always included', // spec
  lineHint: '(a marker at every line of the script, not only at each scene)', // spec
  packButton: 'Pack for Resolve', // spec
  doneText: 'Done. Your files are in the "SceneVoice" folder in your Documents folder:', // spec (untrue for dev/--workspace launches: record, do not change)
  timelineFile: 'resolve_timeline', // spec
  timelineNote: '(import this into Resolve)', // spec
  manifestFile: 'scene_manifest', // spec
  manifestNote: '(a spreadsheet of the scenes, for any editor)', // spec
  audioDir: 'audio/', // spec
  audioNote: '(one sound file per scene)', // spec
  showInFinder: 'Show in Finder', // spec
  downloadZip: 'Download as zip', // spec
  resolveHint:
    'In Resolve: File > Import > Timeline, then choose "resolve_timeline". Using a different editor? Import the audio files and use the spreadsheet to place them.', // spec
  cancelNote: 'Stopping. A scene being listened to may still have used OpenRouter quota.',
  stopped:
    'Stopped. Check the current line-marker status above. A scene being listened to when you stopped may still have used OpenRouter quota.',
  alignHeading: 'SceneVoice could not update the line markers.',
  packHeading: 'SceneVoice could not pack this script.',
  footer:
    'Nothing was saved. Scenes already listened to were paid for, and Try again listens to every scene that needs it again. You can also pack without updating the line markers.',
  generic: 'SceneVoice could not finish. Try again.',
  needsVoice: 'Packing needs every scene voiced first.',
  backToVoice: 'Back to voice',
  busy: 'SceneVoice is busy with another job. This works again when it finishes.',
  ended: 'This step has ended. Check the markers below, then carry on.',
  nextPack: 'Next: Pack',
  tryAgain: 'Try again',
  checkDetails: 'Check my details',
  back: 'Back',
  // The five OpenRouter sentences, copied by value from beats/flow.ts.
  badKey: 'OpenRouter did not accept your key. Check that you pasted all of it.',
  noCredit: 'Your OpenRouter account has no credit left. Add credit there, then try again.',
  tooMany: 'OpenRouter says there have been too many requests, or your allowance is used up. Wait a little, then try again.',
  down: 'OpenRouter had a problem. Try again in a minute.',
  connection:
    'The request failed or timed out, and may still have been charged. Check your internet connection, then try again in a minute.'
} as const;

/** "scene 2", "scenes 2 and 5", "scenes 2, 3 and 5", or "4 scenes" past the list limit. */
export function sceneList(scenes: readonly number[]): string {
  if (scenes.length > LIST_LIMIT) return `${scenes.length} scenes`;
  if (scenes.length === 1) return `scene ${scenes[0]}`;
  return `scenes ${scenes.slice(0, -1).join(', ')} and ${scenes[scenes.length - 1]}`;
}

export type LineMarkers = { state: 'none' | 'unreadable' | 'fresh' | 'stale'; stale_scenes: number[] };

/** The status text (no "Line markers" prefix). `stale_scenes` also holds never-aligned scenes, so it says "changed"
 * only for a listed count; an empty list is just "Out of date". */
export function markersLine(markers: LineMarkers | undefined): string {
  switch (markers?.state) {
    case 'fresh':
      return PACK_WORDS.statusFresh;
    case 'unreadable':
      return PACK_WORDS.statusUnreadable;
    case 'stale': {
      const scenes = markers.stale_scenes;
      if (scenes.length === 0) return 'Out of date';
      return `Out of date (${sceneList(scenes)} changed since they were made)`;
    }
    default:
      return PACK_WORDS.statusNone;
  }
}

/** "Update line markers: N scenes will be listened to. This uses your OpenRouter quota." (spec; singular proposed). */
export function confirmSentence(count: number): string {
  const scenes = count === 1 ? '1 scene will' : `${count} scenes will`;
  return `Update line markers: ${scenes} be listened to. This uses your OpenRouter quota.`;
}

/** "K of N scenes" (approved). */
export function progressLine(done: number, total: number): string {
  return `${done} of ${total} scenes`;
}

/** "Scene N: waiting|listening|done" (approved). */
export function rowLine(ordinal: number, status: 'waiting' | 'listening' | 'done'): string {
  return `Scene ${ordinal}: ${PACK_WORDS[status]}`;
}
