'use client';
import NextLink, { useLinkStatus } from 'next/link';
import type { ComponentProps, ReactNode } from 'react';
import { LoaderCircle } from 'lucide-react';

function PendingHint() {
  const { pending } = useLinkStatus();
  return <span className={`link-pending-indicator ${pending ? 'is-pending' : ''}`} role="status"><LoaderCircle size={15} className="spin"/>{pending && <span className="sr-only">Opening page…</span>}</span>;
}
export default function NavigationLink({ children, className = '', ...props }: ComponentProps<typeof NextLink> & { children: ReactNode }) {
  return <NextLink {...props} className={`navigation-link ${className}`}>{children}<PendingHint/></NextLink>;
}
