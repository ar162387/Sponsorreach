import SupportConsole from '@/components/support-console';
export const metadata={title:'Support',robots:{index:false,follow:false}};
import {verifiedUser} from '@/lib/server';
import {redirect} from 'next/navigation';
export default async function Page(){if(!await verifiedUser())redirect('/account');return <SupportConsole/>;}
