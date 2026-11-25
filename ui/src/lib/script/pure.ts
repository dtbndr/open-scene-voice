// Pure helpers of the script model: line endings, upload decode, Show line offsets, the latest-answer guard.

export const UPLOAD_LIMIT = 1_048_576;
export const TOO_LARGE = 'This file is larger than 1 MiB, so it cannot be opened here.';
export const NOT_UTF8 = 'This file is not valid UTF-8 text, so it cannot be opened here.';
export const LINE_ENDINGS_NOTE =
  'This script uses Windows-style line endings or a hidden marker at the start. Save it to fix them; the words do not change.';

/** CRLF and lone CR become LF and one leading U+FEFF is dropped. These are not wording; the browser is never relied on. */
export function normalise(text: string): { text: string; changed: boolean } {
  const stripped = text.startsWith('﻿') ? text.slice(1) : text;
  const unified = stripped.replace(/\r\n?/g, '\n');
  return { text: unified, changed: unified !== text };
}

export type UploadResult = { ok: true; text: string } | { ok: false; message: string };

/** Size first (before any read is the caller's job), then a fatal UTF-8 decode that keeps a leading byte-order mark. */
export function decodeUpload(bytes: ArrayBuffer): UploadResult {
  if (bytes.byteLength > UPLOAD_LIMIT) return { ok: false, message: TOO_LARGE };
  try {
    return { ok: true, text: new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes) };
  } catch {
    return { ok: false, message: NOT_UTF8 };
  }
}

/** The offsets of line `line` (1-based) in `text`, end exclusive and without its newline; past the end clamps to the last line. */
export function lineRange(text: string, line: number): { start: number; end: number } {
  const lines = text.split('\n');
  const index = Math.min(Math.max(Math.floor(line), 1), lines.length) - 1;
  let start = 0;
  for (let i = 0; i < index; i += 1) start += lines[i].length + 1;
  return { start, end: start + lines[index].length };
}

/** Hands out numbers; only the most recent one is still current, so an older answer is dropped. */
export class LatestOnly {
  #latest = 0;
  next(): number {
    this.#latest += 1;
    return this.#latest;
  }
  isLatest(generation: number): boolean {
    return generation === this.#latest;
  }
}
