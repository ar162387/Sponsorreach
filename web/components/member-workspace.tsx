'use client';
import {usePathname,useSearchParams} from 'next/navigation';
import {useState} from 'react';
import Account from './account';
import MemberOverview from './member-overview';
import Billing from './billing';
import SupportConsole from './support-console';
export default function MemberWorkspace({children}:{children:React.ReactNode}){
 const path=usePathname(),signin=useSearchParams().get('signin'),research=['/account/search','/account/shortlists','/account/saved'].includes(path);
 const [researchVisited,setResearchVisited]=useState(research);
 if(research&&!researchVisited)setResearchVisited(true);
 return <>{(research||researchVisited)&&<div hidden={!research}><Account authenticated/></div>}{path==='/account'?<>{signin==='association_failed'&&<p className="notice" role="status">You’re signed in. If a recent shortlist is missing, open it in the browser where you started the search and try again.</p>}<MemberOverview/></>:path==='/account/billing'?<Billing/>:path==='/account/support'?<SupportConsole/>:research?null:children}</>;
}
