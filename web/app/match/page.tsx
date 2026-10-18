import type { Metadata } from 'next';
import Intake from '@/components/intake';
export const metadata: Metadata = { title: 'Build your sponsor shortlist', description: 'Share your degree, skills and preferences to find relevant UK licensed sponsor companies. Preview up to three matches free.' };
export default function MatchPage() { return <Intake/>; }
