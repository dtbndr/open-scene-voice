// The confirmation snapshot (U8): the numbers a creator confirms are computed once from the detail, mirroring the
// server's job_scenes / job_echo / align_echo, then frozen. The start body is built from the snapshot alone.
import type { JobKind, JobMode, ProjectDetail, StartBody } from './types';

export interface SnapshotInputs {
  voice?: string;
  language?: string;
  instruction?: string;
}

export interface Snapshot {
  readonly kind: JobKind;
  readonly mode: JobMode | null;
  readonly scene: number | null;
  readonly scenes: number | null;
  readonly characters: number | null;
  readonly model: string | null;
  readonly revision: string | null;
  readonly voice: string | null;
  readonly language: string | null;
  readonly instruction: string | null;
}

function need<T>(value: T | null | undefined, what: string): T {
  if (value === null || value === undefined || value === '') throw new Error(`confirm: missing ${what}`);
  return value;
}

function count(value: unknown, what: string): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) throw new Error(`confirm: bad ${what}`);
  return value;
}

/** Map the detail once, when the confirmation opens. `model` is the creator's choice; for `rest` and `synth-scene` it is ignored and the recorded model is used (error if none). */
export function snapshotFor(
  kind: JobKind,
  mode: JobMode | null,
  detail: ProjectDetail,
  scene?: number,
  model?: string,
  inputs: SnapshotInputs = {}
): Snapshot {
  if ((kind === 'synth') !== (mode !== null)) throw new Error('confirm: mode belongs to synth only');
  const revision = need(detail.script?.revision, 'revision');
  const planned = detail.script.scenes;
  let scenes: number | null = null;
  let characters: number | null = null;
  let chosenModel: string | null = null;
  const recorded = detail.audio?.settings?.model ?? null;

  if (kind === 'pack') {
    return Object.freeze(blank(kind, mode));
  }
  if (kind === 'align') {
    scenes = count(detail.line_markers?.listen_scenes, 'listen_scenes');
    return Object.freeze({ ...blank(kind, mode), scenes, revision });
  }

  let picked = planned;
  if (kind === 'synth-scene') {
    if (typeof scene !== 'number' || !Number.isInteger(scene) || scene < 1) throw new Error('confirm: bad scene');
    picked = planned.filter((entry) => entry.ordinal === scene);
    if (picked.length === 0) throw new Error('confirm: scene is not in the script');
  } else if (kind === 'synth' && mode === 'rest') {
    const voiced = new Set((detail.audio?.scenes ?? []).filter((entry) => entry.voiced).map((entry) => entry.ordinal));
    picked = planned.filter((entry) => !voiced.has(entry.ordinal));
  }
  scenes = picked.length;
  characters = picked.reduce((sum, entry) => sum + count(entry.characters, 'scene characters'), 0);

  const fromRecord = kind === 'synth-scene' || (kind === 'synth' && mode === 'rest');
  // Rest and synth-scene run on the recorded settings: a differing model would only earn a 409, so it is never sent.
  chosenModel = need(fromRecord ? recorded : model, 'model');
  const voice = kind === 'synth' && (mode === 'all' || mode === 'restart') ? need(inputs.voice, 'voice') : null;
  const withText = voice !== null;
  return Object.freeze({
    ...blank(kind, mode),
    scene: kind === 'synth-scene' ? (scene as number) : null,
    scenes,
    characters,
    model: chosenModel,
    revision,
    voice,
    language: withText ? (inputs.language || null) : null,
    instruction: withText ? (inputs.instruction || null) : null
  });
}

function blank(kind: JobKind, mode: JobMode | null) {
  return {
    kind,
    mode,
    scene: null,
    scenes: null,
    characters: null,
    model: null,
    revision: null,
    voice: null,
    language: null,
    instruction: null
  } as {
    kind: JobKind;
    mode: JobMode | null;
    scene: number | null;
    scenes: number | null;
    characters: number | null;
    model: string | null;
    revision: string | null;
    voice: string | null;
    language: string | null;
    instruction: string | null;
  };
}

/** The POST /jobs body from the snapshot alone (parse_job_request / job_settings define the shape). */
export function startBody(snapshot: Snapshot): StartBody {
  const { kind } = snapshot;
  if (kind === 'pack') return { kind };
  const revision = need(snapshot.revision, 'revision');
  const scenes = count(snapshot.scenes, 'scenes');
  if (kind === 'align') return { kind, confirm: { scenes, revision } };
  const characters = count(snapshot.characters, 'characters');
  const model = need(snapshot.model, 'model');
  const confirm = { scenes, characters, model, revision };
  if (kind === 'synth-scene') return { kind, scene: need(snapshot.scene, 'scene'), confirm };
  if (kind === 'beats' || kind === 'beats-redo') return { kind, model, confirm };
  const mode = need(snapshot.mode, 'mode');
  if (mode === 'rest') return { kind, mode, confirm };
  const body: StartBody = { kind, mode, voice: need(snapshot.voice, 'voice'), model, confirm };
  if (snapshot.language) body.language = snapshot.language;
  if (snapshot.instruction) body.instruction = snapshot.instruction;
  return body;
}
