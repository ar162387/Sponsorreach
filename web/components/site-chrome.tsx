'use client';
import {usePathname} from 'next/navigation';
export default function SiteChrome({children,signedIn}:{children:React.ReactNode;signedIn:boolean}){const path=usePathname();return signedIn&&/^\/(account|admin)(\/|$)/.test(path)?null:<>{children}</>;}
