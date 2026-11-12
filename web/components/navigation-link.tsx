'use client';
import NextLink, { useLinkStatus } from 'next/link';
import type { ComponentProps, ReactNode } from 'react';
import {useWorkspaceRouter} from './workspace-navigation';
import { LoaderCircle } from 'lucide-react';

function PendingHint() {
  const { pending } = useLinkStatus();
  return <span className={`link-pending-indicator ${pending ? 'is-pending' : ''}`} role="status"><LoaderCircle size={15} className="spin"/>{pending && <span className="sr-only">Opening page…</span>}</span>;
}
export default function NavigationLink({ children, className = '', ...props }: ComponentProps<typeof NextLink> & { children: ReactNode }) {
  const router=useWorkspaceRouter();
  const local=typeof props.href==='string'&&router.canNavigate(props.href);
  return <NextLink {...props} prefetch={local?false:props.prefetch} className={`navigation-link ${className}`} onClick={event=>{
    props.onClick?.(event);
    if(!local||event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey||props.target==='_blank')return;
    event.preventDefault();if(props.replace)router.replace(String(props.href),{scroll:props.scroll});else router.push(String(props.href),{scroll:props.scroll});
  }}>{children}{!local&&<PendingHint/>}</NextLink>;
}
