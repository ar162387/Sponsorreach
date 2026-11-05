'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {api} from '@/lib/types';
import {CREDITS_CHANGED} from './dashboard-shell';
type Allowance={credit_mode:boolean;available:number;preview_available:boolean};
export default function CreditAllowance({onBalance}:{onBalance?:(balance:number)=>void}) {
  const [state,setState]=useState<Allowance|null>(null);
  useEffect(()=>{
    let active=true;
    const controller=new AbortController();
    async function load(){try{const result=await api<Allowance>('account/allowance',{signal:controller.signal});if(active){setState(result);if(result.credit_mode)onBalance?.(result.available);}}catch{/* Billing and the server remain authoritative if a refresh fails. */}}
    void load();window.addEventListener(CREDITS_CHANGED,load);window.addEventListener('focus',load);
    return()=>{active=false;controller.abort();window.removeEventListener(CREDITS_CHANGED,load);window.removeEventListener('focus',load);};
  },[onBalance]);
  if(!state?.credit_mode||state.available>0)return null;
  return <p className="error" role="alert">Your credits are used up. Your profile and saved research are safe. <Link href="/account/billing">Get more credits</Link></p>;
}
