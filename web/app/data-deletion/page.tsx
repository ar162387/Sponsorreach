import { cookies } from 'next/headers';
import Link from 'next/link';

export const metadata = {
  title: 'Data deletion',
  description: 'How to delete your SponsorReach account or request deletion of information from Facebook Login or Google sign-in.',
};

const contact = 'privacy@sponsorreach.uk';

export default async function Page() {
  const receipt = (await cookies()).get('sr_closure_receipt')?.value;
  const date = receipt ? new Date(receipt) : null;
  const deadline = date && Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'long', timeStyle: 'short', timeZone: 'UTC',
  }).format(date) + ' UTC' : null;

  return <article className="legal shell">
    <p className="eyebrow">YOUR INFORMATION</p>
    <h1>Data <em>deletion.</em></h1>
    {deadline && <section className="notice" role="status">
      <h2>Your account deletion is scheduled</h2>
      <p>Your account is locked and scheduled for permanent deletion on <strong>{deadline}</strong>.</p>
      <p>To request restoration before then, email <a href={'mailto:' + contact}>{contact}</a> from your account email.</p>
    </section>}
    <h2>Delete your SponsorReach account</h2>
    <ol>
      <li>Sign in to SponsorReach and open <Link href="/account/settings">Account Settings</Link>.</li>
      <li>Choose <strong>Delete account</strong> and confirm with the code we send to your account email.</li>
      <li>We lock the account and schedule permanent deletion after 30 days. Paid renewals stop when you request closure. We send an email with the scheduled date.</li>
    </ol>
    <p>You can request restoration before the scheduled date by emailing <a href={'mailto:' + contact}>{contact}</a>. We’ll verify that you own the account before restoring access.</p>
    <h2>Request deletion by email</h2>
    <p>If you can’t sign in, want to make a direct erasure request, or want us to delete data received through Facebook Login or Google sign-in, email <a href={'mailto:' + contact + '?subject=SponsorReach%20data%20deletion'}>{contact}</a>. Include the email address you used for SponsorReach and tell us whether you want provider data or the entire account deleted. We may ask you to verify ownership. Please keep passwords and sign-in codes private.</p>
    <p>We handle provider-data and direct erasure requests promptly. You can also disconnect Facebook or Google from <Link href="/account/settings">Account Settings</Link> while keeping your SponsorReach account.</p>
    <h2>What happens to your data</h2>
    <p>Permanent account deletion removes your sign-in details, profile, shortlists, saved employers and support content. We may retain limited payment and dispute records where required. See the <Link href="/privacy">privacy notice</Link> for details.</p>
  </article>;
}
