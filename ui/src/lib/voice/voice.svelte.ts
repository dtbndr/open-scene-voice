// The voice model: the phase of the start flow plus the choice fields. The rules live in `flow.ts` (pure). The fields are
// page-local and never stored; no secret is held here.
import type { Catalog } from '../api/types';
import { providerOf, transition, type VoiceAction, type VoiceMode, type VoicePhase } from './flow';

const DEFAULT_GEMINI_VOICE = 'Leda';

export class VoiceModel {
  phase = $state.raw<VoicePhase>({ phase: 'choose' });
  mode = $state<VoiceMode>('all');
  /** "Start again" was pressed on a fully voiced project. */
  again = $state(false);
  modelId = $state('');
  /** A Gemini voice name, or a pasted ElevenLabs ID: one field each, so switching provider keeps what was typed. */
  geminiVoice = $state(DEFAULT_GEMINI_VOICE);
  pastedVoiceId = $state('');
  language = $state('');
  style = $state('');
  /** The server's or the page's words for a refused or failed step. */
  notice = $state<string | null>(null);

  /** Back to a fresh choice view: called when the project changes, never carries a phase over. */
  reset(): void {
    this.phase = { phase: 'choose' };
    this.again = false;
    this.notice = null;
  }

  /** Defaults from the catalog, set once per project visit. */
  init(catalog: Catalog, mode: VoiceMode, firstModel: string): void {
    this.mode = mode;
    this.modelId = firstModel;
    this.language = catalog.default_language;
    this.style = '';
    this.pastedVoiceId = '';
    const names = Object.values(catalog.providers).flatMap((spec) => spec.voices ?? []);
    this.geminiVoice = names.includes(DEFAULT_GEMINI_VOICE) ? DEFAULT_GEMINI_VOICE : (names[0] ?? '');
  }

  /** The voice that would be sent for the chosen model; empty means none chosen yet. */
  voiceFor(catalog: Catalog): string {
    const spec = providerOf(catalog, this.modelId);
    return (spec?.voices === null ? this.pastedVoiceId : this.geminiVoice).trim();
  }

  send(action: VoiceAction): void {
    this.phase = transition(this.phase, action);
  }
}
