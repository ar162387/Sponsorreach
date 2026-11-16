import { signinDestination, signinUrl } from '@/lib/signin-destination';
import MemberOverview from '@/components/member-overview';
import {verifiedUser} from '@/lib/server';
import {redirect} from 'next/navigation';
export const metadata={title:'Your workspace',robots:{index:false,follow:false}};
export default async function Page({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
  const user=await verifiedUser();
  const params=await searchParams;
  const destination = params.new === '1' ? '/account/shortlists?new=1'
    : typeof params.shortlist === 'string'
      ? '/account/shortlists?' + new URLSearchParams({ shortlist: params.shortlist, ...(params.edit === '1' ? { edit: '1' } : {}) })
      : signinDestination(params.returnTo);
  if (!user) redirect(signinUrl(typeof params.signin === 'string' ? params.signin : 'open', signinDestination(destination)));
  if (destination !== '/account') redirect(destination);
  return <MemberOverview/>;
}
