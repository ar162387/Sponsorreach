import { redirect } from 'next/navigation';

export default async function Page({ searchParams }: { searchParams: Promise<{ run?: string }> }) {
  const { run } = await searchParams;
  redirect(typeof run === 'string' && /^[a-f0-9-]{36}$/.test(run)
    ? '/account/shortlists?run=' + run
    : '/account/shortlists?new=1');
}
