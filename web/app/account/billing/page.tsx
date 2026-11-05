import Billing from '@/components/billing';
export const metadata={title:'Credits and usage'};
import {verifiedUser} from '@/lib/server';
import {redirect} from 'next/navigation';
export default async function Page(){if(!await verifiedUser())redirect('/account');return <Billing/>;}
