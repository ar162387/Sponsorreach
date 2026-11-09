'use client';
import {usePathname,useSearchParams} from 'next/navigation';
import Account from './account';
export default function MemberWorkspace({children}:{children:React.ReactNode}){const path=usePathname(),signin=useSearchParams().get('signin'),research=['/account/search','/account/shortlists','/account/saved'].includes(path);return <><div hidden={!research}><Account authenticated/></div>{path==='/account'&&signin==='association_failed'&&<p className="notice" role="status">You’re signed in. If a recent shortlist is missing, open it in the browser where you started the search and try again.</p>}{!research&&children}</>;}
