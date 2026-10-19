import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { verifiedUser } from '@/lib/server';
import Results from '@/components/results';
export const metadata: Metadata = { title: 'Your sponsor shortlist', robots: { index: false, follow: false } };
export default async function ResultPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; if (await verifiedUser()) redirect('/account?shortlist=' + encodeURIComponent(id)); return <Results id={id}/>; }
