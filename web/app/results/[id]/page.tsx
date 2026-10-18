import type { Metadata } from 'next';
import Results from '@/components/results';
export const metadata: Metadata = { title: 'Your sponsor shortlist', robots: { index: false, follow: false } };
export default async function ResultPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <Results id={id}/>; }
