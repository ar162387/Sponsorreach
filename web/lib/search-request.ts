import type { Profile, VisaContext } from './types';

export function searchRequest({ profile, sourceSession, identity, visaContext, creditConsent, idempotencyKey }: {
  profile: Profile;
  sourceSession?: string;
  identity?: { name: string; email: string };
  visaContext: VisaContext | null;
  creditConsent: boolean;
  idempotencyKey: string;
}) {
  return {
    profile: { ...profile, explore: false, role_intents: profile.role_intents.map(role => ({ ...role, confirmed: true })) },
    // The create and refresh endpoints have different strict request schemas.
    ...(sourceSession ? { accept_credit_cost: creditConsent } : { identity }),
    visa_context: visaContext,
    idempotency_key: idempotencyKey,
  };
}
