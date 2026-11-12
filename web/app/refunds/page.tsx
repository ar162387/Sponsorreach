import SubscriptionPolicy from '@/components/subscription-policy';
import type { Metadata } from 'next';
export const metadata: Metadata = { title: '€24.99 monthly subscription, payments and refunds' };
export default function Refunds() { return <article className="legal shell"><p className="eyebrow">SUBSCRIPTION INFORMATION · UPDATED 4 NOVEMBER 2026</p><h1>Payments and <em>refunds.</em></h1><SubscriptionPolicy/></article>; }
