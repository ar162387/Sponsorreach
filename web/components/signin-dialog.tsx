'use client';

import Image from 'next/image';
import Link from 'next/link';
import { X } from 'lucide-react';
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import EmailSignin from './email-signin';
import { SocialButtons, VerifySocial } from './social-signin';
import { signinUrl } from '@/lib/signin-destination';
import s from './signin-dialog.module.css';

type SigninRequest = {
  destination: string;
  notice?: string;
  closed?: boolean;
  pending?: { provider: 'google' | 'facebook'; email?: string };
};

const SigninContext = createContext<{
  signedIn: boolean;
  isOpen: boolean;
  open: (request: SigninRequest) => void;
} | null>(null);

export function SigninProvider({ children, signedIn, emailAvailable, googleClientId }: {
  children: ReactNode;
  signedIn: boolean;
  emailAvailable: boolean;
  googleClientId: string;
}) {
  const [request, setRequest] = useState<SigninRequest>();
  const isOpen = !signedIn && !!request;
  return <SigninContext.Provider value={{ signedIn, isOpen, open: setRequest }}>
    {children}
    {isOpen && <SigninDialog request={request} emailAvailable={emailAvailable}
      googleClientId={googleClientId} onClose={() => setRequest(undefined)}/>}
  </SigninContext.Provider>;
}

export function SigninLink({ destination = '/account', className, children }: {
  destination?: string;
  className?: string;
  children: ReactNode;
}) {
  const signin = useContext(SigninContext);
  if (signin?.signedIn) return <Link href={destination} className={className}>{children}</Link>;
  return <Link href={signinUrl('open', destination)} className={className} prefetch={false} aria-haspopup="dialog"
    onClick={event => {
      if (!signin || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      signin.open({ destination });
    }}>{children}</Link>;
}

export function useSigninDialogOpen() {
  return useContext(SigninContext)?.isOpen ?? false;
}

export function OpenSigninOnArrival({ request }: { request: SigninRequest }) {
  const open = useContext(SigninContext)?.open;
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.pathname !== '/' || !url.searchParams.has('signin')) return;
    url.searchParams.delete('signin');
    url.searchParams.delete('returnTo');
    window.history.replaceState(null, '', url.pathname + url.search + url.hash);
    open?.(request);
  }, [open, request]);
  return null;
}

function SigninDialog({ request, emailAvailable, googleClientId, onClose }: {
  request: SigninRequest;
  emailAvailable: boolean;
  googleClientId: string;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    const element = dialog.current;
    if (!element || element.open) return;
    element.showModal();
    element.querySelector('input')?.focus();
  }, []);

  const isSignup = request.destination === '/account/search';
  const complete = useCallback((next: string) => {
    if (next === '/account?signin=verify') {
      window.location.assign(signinUrl('verify', request.destination));
    } else {
      window.location.assign(next === '/account' || next === '/account?new=1' ? request.destination : next);
    }
  }, [request.destination]);

  const google = googleClientId && <>
    {emailAvailable && <div className={s.divider}><span>or</span></div>}
    <SocialButtons googleClientId={googleClientId} onComplete={complete}/>
  </>;

  return <dialog ref={dialog} className={s.dialog} aria-labelledby="signin-dialog-title"
    aria-describedby="signin-dialog-description" onClose={onClose}
    onClick={event => { if (event.target === event.currentTarget) event.currentTarget.close(); }}>
    <div className={s.content}>
      <button type="button" className={s.close} aria-label="Close sign-in dialog" onClick={() => dialog.current?.close()}>
        <X size={20} aria-hidden="true"/>
      </button>
      <div className={s.brand}><Image src="/brand/sr-mark-navy.png" width={28} height={16} alt=""/></div>
      <h2 id="signin-dialog-title">{isSignup ? 'Start for free' : 'Sign in to SponsorReach'}</h2>
      <p className={s.description} id="signin-dialog-description">
        {isSignup ? 'Get 5 free research credits when you verify your email.' : googleClientId ? 'Continue with your email or Google account.' : 'We’ll email you a one-time sign-in code.'}
      </p>
      {request.notice && <p className={s.notice} role="status">{request.notice}</p>}
      {request.closed && <Link className={s.help} href="/data-deletion" onClick={() => dialog.current?.close()}>Get help with a deletion request</Link>}
      {request.pending
        ? <VerifySocial {...request.pending} linking={false} onComplete={complete} onCancel={() => dialog.current?.close()}/>
        : emailAvailable
          ? <EmailSignin inDialog onComplete={complete} alternatives={google}/>
          : <><p className={s.notice} role="status">Email sign-in is temporarily unavailable.</p>{google}</>}
    </div>
  </dialog>;
}
