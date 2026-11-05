import type { Metadata } from 'next';
export const metadata: Metadata = { alternates: { canonical: 'https://sponsorreach.uk' } };
import { verifiedUser } from '@/lib/server';
import MarketingHome from '@/components/marketing-home';
import {redirect} from 'next/navigation';
export default async function Home() {
  const user = await verifiedUser();
  if(user)redirect('/account');
  return <MarketingHome/>;
}
