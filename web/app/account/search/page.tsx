import {redirect} from 'next/navigation';
import {verifiedUser} from '@/lib/server';
export const metadata={title:'New search',robots:{index:false,follow:false}};
export default async function Page(){if(!await verifiedUser())redirect('/account');return null;}
