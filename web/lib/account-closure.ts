import 'server-only';
import { cancel, confirmSession, environment, internal, provider } from './billing-server';
import { memberAccess } from './member-access';

type Job = { user_id: string; request_id: string };
type CheckoutIntent = { id: string; expires_at: string; provider_session: string | null };

async function findUnboundCheckouts(job: Job, intents: CheckoutIntent[]) {
  const missing = new Map(intents.filter(intent => !intent.provider_session).map(intent => [intent.id, intent]));
  if (!missing.size) return;
  for (let offset = 0; offset < 20000; offset += 100) {
    const page = await provider().checkouts.list({ limit: 100, offset });
    for (const remote of page.items) {
      const intentId = remote.metadata?.checkoutIntentId;
      const intent = typeof intentId === 'string' ? missing.get(intentId) : undefined;
      if (intent && remote.metadata?.customerId === job.user_id) {
        await internal('bind', { intent_id: intent.id, user_id: job.user_id, session_id: remote.sessionId,
          url: remote.checkoutUrl, expires_at: remote.expiresAt });
        intent.provider_session = remote.sessionId;
        missing.delete(intent.id);
      }
    }
    if (!missing.size) return;
    if (!page.hasMore) {
      for (const intent of missing.values()) {
        if (Date.parse(intent.expires_at) <= Date.now()) await memberAccess('expire-checkout',
          { ...job, intent_id: intent.id, environment: environment() });
      }
      return;
    }
  }
  throw new Error('Checkout reconciliation requires another pass');
}

export async function processAccountClosure(job: Job) {
  let billingFailed = false;
  try {
    const { checkouts, renewals } = await memberAccess<{
      checkouts: CheckoutIntent[]; renewals: boolean;
    }>('deletion-billing', { ...job, environment: environment() });
    // Stop known renewals even if an in-flight checkout still needs reconciliation.
    if (renewals) await cancel(job.user_id, { skipScheduled: true });
    await findUnboundCheckouts(job, checkouts);
    for (const checkout of checkouts) {
      if (!checkout.provider_session) continue;
      const session = await provider().checkouts.retrieve(checkout.provider_session);
      if (session.status === 'open') {
        const result = await provider().checkouts.cancel(session.sessionId);
        if (!result.success) throw new Error('Checkout cancellation pending');
        await internal('checkout-status', { session_id: session.sessionId, status: 'cancelled' });
      } else {
        const result = await confirmSession(session.sessionId);
        if (result.status === 'completed') await cancel(job.user_id, { skipScheduled: true });
      }
    }
  } catch { billingFailed = true; }
  const result = await memberAccess<{ pending: boolean }>('process-deletion', { ...job, environment: environment() });
  return { pending: billingFailed || result.pending };
}

export async function runAccountClosures() {
  const { jobs } = await memberAccess<{ jobs: Job[] }>('deletion-jobs', {});
  let pending = 0;
  for (const job of jobs) {
    try { if ((await processAccountClosure(job)).pending) pending++; }
    catch { pending++; }
  }
  return { checked: jobs.length, pending };
}
