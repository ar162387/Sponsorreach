import { redirect } from 'next/navigation';
import MemberSettings from '@/components/member-settings';
import { isAdministrator, verifiedUser } from '@/lib/server';
import { closureAvailable, currentAccessToken, memberAccess, socialConfig, type SocialProvider } from '@/lib/member-access';
import { pendingSocial } from '@/lib/social-signin';

export const metadata = { title: 'Account settings', robots: { index: false, follow: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ signin?: string }> }) {
  const user = await verifiedUser();
  if (!user || isAdministrator(user)) redirect('/account');
  const accessToken = await currentAccessToken();
  if (!accessToken) redirect('/account');
  const config = socialConfig();
  const { providers } = await memberAccess<{ providers: SocialProvider[] }>('methods', {}, accessToken);
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
