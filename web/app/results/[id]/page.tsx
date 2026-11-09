import type { Metadata } from 'next';
import {verifiedUser} from '@/lib/server';
import {redirect} from 'next/navigation';
import Results from '@/components/results';
import { socialConfig } from '@/lib/member-access';
export const metadata: Metadata = { title: 'Your sponsor shortlist', robots: { index: false, follow: false } };
export default async function ResultPage({ params, searchParams }: {
  params: Promise<{ id: string }>; searchParams: Promise<{ signin?: string }>;
}) {
  const { id } = await params;
  if (await verifiedUser()) redirect('/account/shortlists?shortlist=' + encodeURIComponent(id));
  const { signin } = await searchParams;
  return <Results id={id} social={socialConfig()} wrongSignInEmail={signin === 'shortlist_email'}/>;
}
