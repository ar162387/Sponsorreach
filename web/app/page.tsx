import { verifiedUser } from '@/lib/server';
import MarketingHome from '@/components/marketing-home';
import Account from '@/components/account';
export default async function Home() {
  const user = await verifiedUser();
  return user ? <Account authenticated dashboard/> : <MarketingHome/>;
}
