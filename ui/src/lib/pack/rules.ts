// Pack decisions (pure): what "Update line markers" does, whether the key popup is needed, whether a download is
// offered. `can` does not carry busy; the controller adds the active-job check.
import type { ProjectDetail } from '../api/types';

export { alignFailureView, packFailureView } from './failure';
export type { AlignFailureView, PackFailureView, PackButton } from './failure';

export type UpdatePlan = 'unavailable' | 'free' | 'paid';

/** Unavailable first (`can.align` false, even with nothing to listen to), then free (`listen_scenes` 0, no dialog,
 * no key check), else paid. A missing count is paid: a confirmation is never skipped on a guess. */
export function updatePlan(detail: ProjectDetail): UpdatePlan {
  if (detail.can?.align !== true) return 'unavailable';
  return detail.line_markers?.listen_scenes === 0 ? 'free' : 'paid';
}

/** The OpenRouter key popup only when something will be listened to. */
export function needsOpenRouterKey(detail: ProjectDetail): boolean {
  return updatePlan(detail) === 'paid';
}

/** pack.zip answers 409 JSON while a job holds the slot, and 404 with no pack; offer it only when it can work. */
export function canDownload(detail: ProjectDetail, jobActive: boolean): boolean {
  return !jobActive && detail.pack?.manifest === true;
}
