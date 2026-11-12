import {Suspense} from 'react';
import { redirect } from 'next/navigation';
import MemberSettings from '@/components/member-settings';
import { isAdministrator, verifiedUser } from '@/lib/server';
import { closureAvailable, currentAccessToken, memberAccess, socialConfig, type SocialProvider } from '@/lib/member-access';
import { pendingSocial } from '@/lib/social-signin';

export const metadata = { title: 'Account settings', robots: { index: false, follow: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ signin?: string }> }) {
  const user = await verifiedUser();
  if (!user) redirect('/account');
  if (isAdministrator(user)) return <div className="dashboard-stack"><h1>Account settings</h1><section className="dashboard-card"><h2>Administrator account</h2><p>{user.email}</p></section></div>;
  return <div className="dashboard-stack">
    <h1>Account settings</h1>
    <Suspense fallback={<section className="dashboard-card" aria-busy="true"><h2>Connected sign-in methods</h2><span className="data-placeholder"/></section>}>
      <SettingsControls searchParams={searchParams}/>
    </Suspense>
  </div>;
}

async function SettingsControls({searchParams}:{searchParams:Promise<{signin?:string}>}) {
  const accessToken = await currentAccessToken();
  if (!accessToken) return <section className="dashboard-card"><p>Your session needs to be renewed to manage settings.</p><a href="/account?signin=expired">Return to sign-in</a></section>;
  const config = socialConfig();
  let providers: SocialProvider[];
  try {
    ({providers} = await memberAccess<{providers: SocialProvider[]}>('methods', {}, accessToken));
  } catch {
    return <section className="dashboard-card"><h2>Connected sign-in methods</h2><p>Settings are temporarily unavailable.</p><a href="/account/settings">Try again</a></section>;
  }
  let { signin } = await searchParams;
  let pending;
  if (signin === 'verify') {
    try {
      const attempt = await memberAccess<{ provider: SocialProvider; email?: string; linking: boolean }>('pending', await pendingSocial(), accessToken);
      if (attempt.linking) pending = attempt;
    } catch { /* The member can restart from this page. */ }
    if (!pending) signin = 'expired';
  }
  return <MemberSettings providers={providers} config={config} pending={pending} signin={signin} closureAvailable={closureAvailable()}/>;
}
