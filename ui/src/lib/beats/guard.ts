// The beats route checks only the light shape of the file, so the page type-guards what it renders (item 11):
// an item that does not fit is skipped, and if nothing usable remains the caller shows the invalid-file message.
import type { BeatsDocument } from '../api/types';

export interface BeatLine {
  first: number;
  last: number;
  note: string;
}

export interface BeatsScene {
  ordinal: number;
  title: string;
  beats: BeatLine[];
}

function isInt(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value);
}

function usableBeat(value: unknown): BeatLine | null {
  if (typeof value !== 'object' || value === null) return null;
  const { first, last, note } = value as Record<string, unknown>;
  return isInt(first) && isInt(last) && typeof note === 'string' ? { first, last, note } : null;
}

function usableScene(value: unknown): BeatsScene | null {
  if (typeof value !== 'object' || value === null) return null;
  const { ordinal, title, beats } = value as Record<string, unknown>;
  if (!isInt(ordinal) || typeof title !== 'string' || !Array.isArray(beats)) return null;
  const lines = beats.map(usableBeat).filter((beat): beat is BeatLine => beat !== null);
  return { ordinal, title, beats: lines };
}

/** The scenes that fit; an empty list means the file is not usable. */
export function usableScenes(document: BeatsDocument): BeatsScene[] {
  if (!Array.isArray(document?.scenes)) return [];
  return document.scenes.map(usableScene).filter((scene): scene is BeatsScene => scene !== null);
}

export function rangeWords(first: number, last: number): string {
  return first === last ? `Sentence ${first}` : `Sentences ${first} to ${last}`;
}
