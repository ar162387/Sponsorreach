import type { Metadata } from 'next';
import Intake from '@/components/intake';
export const metadata: Metadata = { title: 'Build your sponsor shortlist', description: 'Share your degree, skills and preferences to find relevant UK licensed sponsor companies. Preview up to three matches free.' };
export default async function MatchPage({ searchParams }: { searchParams: Promise<{ shortlist?: string; new?: string }> }) {
  const query = await searchParams;
  const shortlist = query.shortlist && /^[a-f0-9-]{36}$/.test(query.shortlist) ? query.shortlist : undefined;
  return <Intake key={shortlist || (query.new ? 'new' : 'draft')} sourceSession={shortlist} newSearch={query.new === '1'}/>;
}
