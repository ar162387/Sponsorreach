import { redirect } from 'next/navigation';
import { verifiedUser } from '@/lib/server';
import { signinUrl } from '@/lib/signin-destination';

export const metadata = { title: 'Your shortlists', robots: { index: false, follow: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ new?: string }> }) {
  if (!await verifiedUser()) {
    const { new: newSearch } = await searchParams;
    redirect(signinUrl('open', newSearch === '1' ? '/account/shortlists?new=1' : '/account/shortlists'));
  }
  return null;
}
