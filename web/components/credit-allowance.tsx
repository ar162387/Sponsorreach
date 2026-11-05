 'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {api} from '@/lib/types';
export default function CreditAllowance(){const[state,setState]=useState<{credit_mode:boolean;available:number;preview_available:boolean}|null>(null);useEffect(()=>{let active=true;api<{credit_mode:boolean;available:number;preview_available:boolean}>('account/allowance').then(r=>{if(active)setState(r);}).catch(()=>{});return()=>{active=false;};},[]);if(!state?.credit_mode)return null;return <p className="notice">{state.available} credits available. {state.available===0?'Your credits are used up. Subscribe to continue searching.':'Each new search uses 1 credit when results arrive. Failed or empty searches use no credits.'} <Link href="/account/billing">Manage credits</Link></p>;}
