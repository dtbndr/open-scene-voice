// Voicing failure views (pure): wording and buttons per failure kind and provider. Not the beats wording.
// APPROVED (spec "Waiting and errors"): Google bad_key, ElevenLabs provider_down and quota, with their buttons.
// PROPOSED (owner gate): everything marked below, including the provider name filled in for the other provider.
import { FIXED_MESSAGE } from '../api/errors';
import type { Catalog, ProjectDetail } from '../api/types';
import type { VoiceFailure, VoiceMode } from './flow';
export type ProviderName = 'google' | 'elevenlabs';
export type FailureButton = 'checkDetails' | 'tryAgain' | 'back';
export interface VoiceFailureView {
  heading?: string;
  text: string;
  buttons: FailureButton[];
}
const NAMES: Record<ProviderName, string> = { google: 'Google Cloud', elevenlabs: 'ElevenLabs' };
export const FAILURE_WORDS = {
  googleBadKey:
    'Google Cloud did not accept your details. Check that you pasted all of the key, that the project ID and region are right, and that the account is active.',
  elevenBadKey: 'ElevenLabs did not accept your key. Check that you pasted all of it and that the account is active.', // PROPOSED
  invalidHeading: 'SceneVoice could not voice this script.', // PROPOSED
  generic: 'Voicing did not finish. Scenes already voiced are kept.', // PROPOSED
  checkDetails: 'Check my details', // approved (Google bad_key); proposed for ElevenLabs
  tryAgain: 'Try again',
  back: 'Back'
} as const;
/** Which provider a catalog entry is: the ElevenLabs key means ElevenLabs, anything else is Google Cloud. */
export function providerName(spec: Catalog['providers'][string] | null): ProviderName {
  return spec?.env_names.includes('ELEVENLABS_API_KEY') ? 'elevenlabs' : 'google';
}
export function voiceFailureView(failure: VoiceFailure, provider: ProviderName): VoiceFailureView {
  const name = NAMES[provider];
  switch (failure.kind) {
    case 'bad_key':
      return { text: provider === 'google' ? FAILURE_WORDS.googleBadKey : FAILURE_WORDS.elevenBadKey, buttons: ['checkDetails', 'tryAgain'] };
    case 'provider_down':
      return { text: `${name} did not answer. Scenes already voiced are kept. Try again in a minute.`, buttons: ['tryAgain', 'back'] };
    case 'quota':
      return {
        text: `Your ${name} allowance is used up. Scenes already voiced are kept. Add credit or wait for your allowance to renew, then try again.`,
        buttons: ['tryAgain']
      };
    case 'invalid_input':
      return { heading: FAILURE_WORDS.invalidHeading, text: failure.message || FAILURE_WORDS.generic, buttons: ['back'] };
    default: // other (and missing_key, which the flow sends to the popup instead)
      return { text: failure.message !== '' && failure.message !== FIXED_MESSAGE ? failure.message : FAILURE_WORDS.generic, buttons: ['back'] };
  }
}
/** The mode "Try again" reopens: after a partial run the rest (when the server allows it); else the same mode. */
export function tryAgainMode(can: ProjectDetail['can'], mode: VoiceMode): VoiceMode {
  return (mode === 'all' || mode === 'restart') && can?.synth?.rest === true ? 'rest' : mode;
}
