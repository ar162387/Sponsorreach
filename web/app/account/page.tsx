import type { Metadata } from 'next';
import Account from '@/components/account';
export const metadata: Metadata = { title: 'My sponsor shortlists', robots: { index: false, follow: false } };
export default function AccountPage() { return <Account/>; }
