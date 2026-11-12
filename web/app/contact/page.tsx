import type { Metadata } from 'next';
import Link from 'next/link';
export const metadata: Metadata = { title: 'Contact' };
export const dynamic = 'force-dynamic';
export default async function Contact() {
  const support = process.env.SPONSORMATCH_SUPPORT_EMAIL || 'info@sponsorreach.uk';
  const privacy = process.env.SPONSORMATCH_PRIVACY_EMAIL || 'privacy@sponsorreach.uk';
  const operator = process.env.SPONSORMATCH_CONTROLLER_NAME || 'Syed Shah Muhammad Saud trading as CYBERBLITZ';
  return <article className="legal shell"><p className="eyebrow">HELP AND CORRECTIONS</p><h1>Get in <em>touch.</em></h1><h2>Account and research questions</h2><p>For help accessing a saved shortlist or reporting incorrect company information, include your account email and the company or page concerned. Please do not send payment-card details or unnecessary personal information.</p>{support ? <p>Email <a href={'mailto:' + support}>{support}</a></p> : <p>Public support contact details are being finalised. Signed-in users can use account support.</p>}<p>Signed-in customers can also <Link href="/account/support">open a support request</Link> and return there to read replies. Email notifications are not currently sent.</p><h2>Privacy and contact information</h2><p>You can request correction or consideration of removal of company or professional contact information without creating an account.</p>{privacy ? <p>Privacy enquiries <a href={'mailto:' + privacy}>{privacy}</a></p> : <p>A privacy contact has not yet been published. Do not submit sensitive information.</p>}{operator && <p>Service operator {operator}. Business location {process.env.SPONSORMATCH_OPERATOR_ADDRESS || 'Rawalpindi, Pakistan'}.</p>}<h2>Payments</h2><p>Our only subscription is €24.99 per month. Use account billing for receipts, cancellation and first-payment refund requests. A pending refund is not a completed refund. See <Link href="/refunds">payments and refunds</Link> for the policy.</p></article>;
}
