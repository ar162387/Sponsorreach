import { redirect } from 'next/navigation';
export default async function MatchPage({ searchParams }: { searchParams: Promise<{ shortlist?: string }> }) {
 const q=await searchParams;
 redirect(q.shortlist&&/^[a-f0-9-]{36}$/.test(q.shortlist)?'/account?shortlist='+q.shortlist+'&edit=1':'/account?new=1');
}
