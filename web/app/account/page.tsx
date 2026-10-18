import Account from '@/components/account';
import { verifiedUser } from '@/lib/server';
export const metadata = { title: 'My sponsor shortlists' };
export default async function AccountPage() { return <Account authenticated={!!(await verifiedUser())}/>; }
