'use client';
import {usePathname} from 'next/navigation';
import Account from './account';
export default function MemberWorkspace({children}:{children:React.ReactNode}){const path=usePathname(),research=['/account/search','/account/shortlists','/account/saved'].includes(path);return <><div hidden={!research}><Account authenticated/></div>{!research&&children}</>;}
