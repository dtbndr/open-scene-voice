// Shapes the M12 routes answer, written from the server code (src/scenevoice/web). Unknown fields pass through untyped.

export const KEY_NAMES = [
  'GOOGLE_CLOUD_PROJECT',
  'GOOGLE_CLOUD_LOCATION',
  'VERTEX_AUTHORIZATION_KEY',
  'ELEVENLABS_API_KEY',
  'OPENROUTER_API_KEY'
] as const;
export type KeyName = (typeof KEY_NAMES)[number];
/** The two names whose saved value the server shows (the rest are secrets and never come back). */
export const NON_SECRET_NAMES: readonly KeyName[] = ['GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION'];

export interface KeyStatus {
  saved: boolean;
  value?: string;
}
export interface KeysView {
  path: string;
  keys: Record<string, KeyStatus>;
  suggested_region: string;
  ignored_environment: string[];
}

export interface ProjectEntry {
  id: string;
  modified: number;
}
export interface ProjectList {
  workspace: string;
  projects: ProjectEntry[];
}
export interface CreatedProject {
  id: string;
}

export type JobKind = 'synth' | 'synth-scene' | 'beats' | 'beats-redo' | 'align' | 'pack';
export type JobMode = 'all' | 'rest' | 'restart';
export type JobState = 'idle' | 'starting' | 'running' | 'cancelling' | 'done' | 'failed' | 'cancelled';
export type FailureKind = 'missing_key' | 'bad_key' | 'quota' | 'provider_down' | 'invalid_input' | 'other';

export interface JobFailure {
  kind: FailureKind;
  message: string;
  scene: number | null;
  status: number | null;
}
export interface JobInfo {
  kind: JobKind;
  mode: JobMode | null;
  project: string;
  scene: number | null;
  started: boolean;
  finished: boolean;
  completed: boolean;
  total: number;
  scenes_done: number;
  failure: JobFailure | null;
  notice: string | null;
  /** The run id (32 hex): Cancel and the lookup name it. */
  run: string;
}
/** GET /api/jobs/current, also the 202 answer to a job start. */
export interface CurrentJob {
  state: JobState;
  job: JobInfo | null;
}

/** `state` and `end` events carry the current-job JSON plus `seq`; scene, note, ok and fail come from the child. */
export type StateEvent = CurrentJob & { type: 'state'; seq: number };
export type EndEvent = CurrentJob & { type: 'end'; seq: number };
export interface SceneEvent {
  type: 'scene';
  seq: number;
  command: string | null;
  message: string;
  state: 'started' | 'done';
  scene: number | null;
  total: number | null;
  path?: string;
}
export interface NoteEvent {
  type: 'note' | 'ok';
  seq: number;
  command: string | null;
  message: string;
}
export interface FailEvent {
  type: 'fail';
  seq: number;
  command: string | null;
  message: string;
  kind: FailureKind;
  scene: number | null;
  line: number | null;
  status: number | null;
}
export type JobEvent = StateEvent | EndEvent | SceneEvent | NoteEvent | FailEvent;

/** Availability from disk, per kind; it does not carry busy. */
export interface Can {
  synth: { all: boolean; rest: boolean; restart: boolean };
  synth_scene: boolean;
  align: boolean;
  beats: boolean;
  beats_redo: boolean;
  pack: boolean;
}

export interface AudioScene {
  ordinal: number;
  voiced: boolean;
  recorded: boolean;
  wav_matches_record: boolean | null; // null when the scene is unvoiced or unrecorded
  text_matches: boolean | null;
}

export interface AudioSettings {
  voice?: string | null;
  model?: string | null;
  language?: string | null;
  instruction?: string | null;
}

export interface AudioView {
  scenes: AudioScene[];
  extra_ordinals: number[];
  record: unknown;
  settings?: AudioSettings | null;
}

/** GET /api/catalog: `voices` is null when the voice is a pasted ID (ElevenLabs). */
export interface Catalog {
  providers: Record<string, { models: string[]; env_names: string[]; voices: string[] | null }>;
  default_language: string;
}

/** The parts of GET /api/projects/{id} that the confirm builder reads; everything else passes through. */
export interface ProjectDetail {
  script: {
    present?: boolean;
    ok?: boolean;
    revision: string | null;
    problem?: { line: number; message: string } | null;
    scenes: { ordinal: number; title?: string; characters: number }[];
    total_characters: number;
    [field: string]: unknown;
  };
  audio?: AudioView;
  /** `state` is none | fresh | stale | invalid; the page never derives availability from it (use `can`). */
  beats?: { state?: string; [field: string]: unknown };
  /** Availability from disk, per kind; it does not carry busy. */
  can?: Can;
  /** The server always sends all three fields; `stale_scenes` is empty unless `state` is `stale`. */
  line_markers?: { state: 'none' | 'unreadable' | 'fresh' | 'stale'; stale_scenes: number[]; listen_scenes: number };
  /** Which pack outputs exist on disk (scene_manifest.csv, resolve_timeline.otio). */
  pack?: { manifest: boolean; timeline: boolean };
  [field: string]: unknown;
}

/** The body of POST /api/projects/{id}/jobs. */
export interface StartBody {
  kind: JobKind;
  mode?: JobMode;
  scene?: number;
  voice?: string;
  model?: string;
  language?: string;
  instruction?: string;
  confirm?: { scenes: number; characters?: number; model?: string; revision: string };
}

/** GET /api/projects/{id}/script. */
export interface ScriptText {
  text: string;
}
/** POST /api/projects/{id}/check: the first problem only. */
export type CheckAnswer =
  | { ok: true; scenes: number }
  | { ok: false; problems: { line: number; message: string }[] };

/** GET /api/projects/{id}/beats: the sidecar as parsed, light-checked only; the page type-guards what it renders. */
export interface BeatsDocument {
  version: number;
  script_sha256: string;
  scenes: unknown[];
}
