// The beats model: the phase of the start flow plus the model field. The rules live in `flow.ts` (pure); this holds the
// current phase so a screen can read it. The model field is page-local and never stored.
import { transition, type BeatsAction, type BeatsPhase } from './flow';

export class BeatsModel {
  phase = $state.raw<BeatsPhase>({ phase: 'choose' });
  /** Free text, empty at open. */
  modelName = $state('');
  /** The server's words for a refused start (409 busy, changed, not_allowed). */
  notice = $state<string | null>(null);

  /** The model field has something in it after trimming. */
  get hasModel(): boolean {
    return this.modelName.trim() !== '';
  }

  send(action: BeatsAction): void {
    this.phase = transition(this.phase, action);
  }
}
