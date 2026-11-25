// Confirm-body table (U17). Every row is P0: the paid-call confirmation must carry exactly what the creator saw.
import { describe, expect, it } from 'vitest';
import { snapshotFor, startBody } from '../src/lib/api/confirm';
import { transition, type BeatsAction, type BeatsPhase } from '../src/lib/beats/flow';
import { transition as voiceTransition, type VoiceAction, type VoicePhase } from '../src/lib/voice/flow';

const REVISION = 'a'.repeat(64);

function makeDetail() {
  return {
    script: {
      present: true,
      ok: true,
      revision: REVISION,
      problem: null,
      scenes: [
        { ordinal: 1, title: 'One', characters: 10 },
        { ordinal: 2, title: 'Two', characters: 20 },
        { ordinal: 3, title: 'Three', characters: 30 }
      ],
      total_characters: 60
    },
    audio: {
      scenes: [
        { ordinal: 1, voiced: true, recorded: true, wav_matches_record: true, text_matches: true },
        { ordinal: 2, voiced: false, recorded: false, wav_matches_record: null, text_matches: null },
        { ordinal: 3, voiced: false, recorded: false, wav_matches_record: null, text_matches: null }
      ],
      extra_ordinals: [] as number[],
      record: null,
      settings: { voice: 'Leda', model: 'recorded-model', language: 'en-GB', instruction: 'calm' }
    },
    line_markers: { state: 'stale' as const, stale_scenes: [], listen_scenes: 2 }
  };
}

const INPUTS = { voice: 'Leda', language: 'en-GB', instruction: 'warm' };

describe('confirm body', () => {
  it('P0 row 1: the body copies scenes, characters, model and revision exactly from the snapshot', () => {
    const snapshot = snapshotFor('synth', 'all', makeDetail(), undefined, 'model-x', INPUTS);
    expect(startBody(snapshot).confirm).toEqual({ scenes: 3, characters: 60, model: 'model-x', revision: REVISION });
  });

  it('P0 row 2: a later change to the source detail changes neither the snapshot nor the body', () => {
    const detail = makeDetail();
    const snapshot = snapshotFor('synth', 'all', detail, undefined, 'model-x', INPUTS);
    const before = JSON.stringify(startBody(snapshot));
    detail.script.scenes.pop();
    detail.script.total_characters = 1;
    detail.script.revision = 'b'.repeat(64);
    expect(JSON.stringify(startBody(snapshot))).toBe(before);
    expect(Object.isFrozen(snapshot)).toBe(true);
  });

  it('P0 row 3: a missing field throws instead of defaulting', () => {
    const noRevision = makeDetail();
    noRevision.script.revision = null as unknown as string;
    expect(() => snapshotFor('beats', null, noRevision, undefined, 'm')).toThrow();
    expect(() => snapshotFor('beats', null, makeDetail())).toThrow(); // no model
    expect(() => snapshotFor('synth', 'all', makeDetail(), undefined, 'm', { language: 'en-GB' })).toThrow(); // no voice
    expect(() => snapshotFor('synth-scene', null, makeDetail(), 9)).toThrow(); // scene not in the script
    expect(() => snapshotFor('align', null, { script: { revision: REVISION, scenes: [], total_characters: 0 } })).toThrow();
  });

  describe('P0 row 4: request shape per kind', () => {
    it('synth all and restart: mode, voice, model, language, instruction and the full confirm', () => {
      for (const mode of ['all', 'restart'] as const) {
        const body = startBody(snapshotFor('synth', mode, makeDetail(), undefined, 'model-x', INPUTS));
        expect(body).toEqual({
          kind: 'synth',
          mode,
          voice: 'Leda',
          model: 'model-x',
          language: 'en-GB',
          instruction: 'warm',
          confirm: { scenes: 3, characters: 60, model: 'model-x', revision: REVISION }
        });
      }
    });

    it('synth rest: only unvoiced scenes, recorded model in the confirm, no voice or model in the body', () => {
      const body = startBody(snapshotFor('synth', 'rest', makeDetail()));
      expect(body).toEqual({
        kind: 'synth',
        mode: 'rest',
        confirm: { scenes: 2, characters: 50, model: 'recorded-model', revision: REVISION }
      });
    });

    it('synth-scene: keeps its ordinal and counts that scene only', () => {
      const body = startBody(snapshotFor('synth-scene', null, makeDetail(), 2));
      expect(body).toEqual({
        kind: 'synth-scene',
        scene: 2,
        confirm: { scenes: 1, characters: 20, model: 'recorded-model', revision: REVISION }
      });
    });

    it('beats and beats-redo: top-level model, full counts', () => {
      for (const kind of ['beats', 'beats-redo'] as const) {
        const body = startBody(snapshotFor(kind, null, makeDetail(), undefined, 'model-b'));
        expect(body).toEqual({
          kind,
          model: 'model-b',
          confirm: { scenes: 3, characters: 60, model: 'model-b', revision: REVISION }
        });
      }
    });

    it('align: scenes from listen_scenes and the revision, no model or characters', () => {
      const body = startBody(snapshotFor('align', null, makeDetail()));
      expect(body).toEqual({ kind: 'align', confirm: { scenes: 2, revision: REVISION } });
    });

    it('pack: no confirm', () => {
      expect(startBody(snapshotFor('pack', null, makeDetail()))).toEqual({ kind: 'pack' });
    });
  });

  it('P0 row 6 (the confirm the creator saw): synth rest and synth-scene send the recorded model whatever the creator typed; no recorded model is an error', () => {
    const rest = snapshotFor('synth', 'rest', makeDetail(), undefined, 'creator-model');
    expect(rest.model).toBe('recorded-model');
    expect(startBody(rest).confirm).toMatchObject({ model: 'recorded-model' });
    const one = snapshotFor('synth-scene', null, makeDetail(), 2, 'creator-model');
    expect(one.model).toBe('recorded-model');
    expect(startBody(one)).toMatchObject({ confirm: { model: 'recorded-model' } });
    const unrecorded = makeDetail();
    (unrecorded.audio.settings as { model: string | null }).model = null;
    expect(() => snapshotFor('synth', 'rest', unrecorded, undefined, 'creator-model')).toThrow();
    expect(() => snapshotFor('synth-scene', null, unrecorded, 2, 'creator-model')).toThrow();
  });

  it('P0 row 5 (paid call without confirm): only the confirmation\'s confirm reaches posting; a rejected snapshot never posts again', () => {
    const phases: BeatsPhase[] = [
      { phase: 'choose' },
      { phase: 'popup' },
      { phase: 'confirming' },
      { phase: 'starting' },
      { phase: 'running' },
      { phase: 'failed', failure: { kind: 'missing_key', status: null, message: 'm' } },
      { phase: 'cancelled' },
      { phase: 'showing' }
    ];
    const actions: BeatsAction[] = [
      { type: 'press', keysMissing: false },
      { type: 'press', keysMissing: true },
      { type: 'popupDone' },
      { type: 'popupCancel' },
      { type: 'confirm' },
      { type: 'rejected', reason: 'changed' },
      { type: 'rejected', reason: 'not_allowed' },
      { type: 'rejected', reason: 'busy' },
      { type: 'started' },
      { type: 'ended', outcome: 'failed', failure: { kind: 'missing_key', status: null, message: 'm' } },
      { type: 'ended', outcome: 'cancelled' },
      { type: 'ended', outcome: 'done' },
      { type: 'tryAgain' },
      { type: 'back' },
      { type: 'redo' }
    ];
    for (const phase of phases) {
      for (const action of actions) {
        if (phase.phase === 'starting') continue; // already posting; its exits are pinned below
        const allowed = phase.phase === 'confirming' && action.type === 'confirm';
        expect(transition(phase, action).phase === 'starting').toBe(allowed);
      }
    }
    for (const reason of ['changed', 'not_allowed'] as const) {
      expect(transition({ phase: 'starting' }, { type: 'rejected', reason }).phase).toBe('choose');
    }
    expect(transition({ phase: 'popup' }, { type: 'popupDone' }).phase).toBe('confirming');
    expect(transition({ phase: 'failed', failure: { kind: 'other', status: null, message: 'm' } }, { type: 'tryAgain' }).phase).toBe('confirming');
    expect(
      transition({ phase: 'running' }, { type: 'ended', outcome: 'failed', failure: { kind: 'missing_key', status: null, message: 'm' } }).phase
    ).toBe('popup');
  });

  it('P0 row 7 (paid call without confirm, voice flow): only the confirmation\'s confirm reaches posting; popup done, Try again, a rejected snapshot and resumed never post', () => {
    const failed: VoicePhase = { phase: 'failed', failure: { kind: 'other', status: null, message: 'm' } };
    const phases: VoicePhase[] = [
      { phase: 'choose' },
      { phase: 'popup' },
      { phase: 'confirming' },
      { phase: 'running' },
      failed,
      { phase: 'cancelled' },
      { phase: 'showing' }
    ];
    const actions: VoiceAction[] = [
      { type: 'press', keysMissing: false },
      { type: 'press', keysMissing: true },
      { type: 'popupDone' },
      { type: 'popupCancel' },
      { type: 'dismiss' },
      { type: 'resumed' },
      { type: 'confirm' },
      { type: 'rejected', reason: 'changed' },
      { type: 'rejected', reason: 'busy' },
      { type: 'started' },
      { type: 'ended', outcome: 'failed', failure: failed.failure },
      { type: 'ended', outcome: 'cancelled' },
      { type: 'ended', outcome: 'done' },
      { type: 'tryAgain' },
      { type: 'back' },
      { type: 'redo' }
    ];
    for (const phase of phases) {
      for (const action of actions) {
        const allowed = phase.phase === 'confirming' && action.type === 'confirm';
        expect(voiceTransition(phase, action).phase === 'starting').toBe(allowed);
      }
    }
    for (const reason of ['changed', 'not_allowed'] as const) {
      expect(voiceTransition({ phase: 'starting' }, { type: 'rejected', reason }).phase).toBe('choose');
    }
    expect(voiceTransition({ phase: 'popup' }, { type: 'popupDone' }).phase).toBe('confirming');
    expect(voiceTransition(failed, { type: 'tryAgain' }).phase).toBe('confirming');
  });
});
