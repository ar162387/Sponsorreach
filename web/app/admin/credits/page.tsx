import AdminRecords from '@/components/admin-dashboard';
import {environment} from '@/lib/billing-server';
export const metadata={title:'Credits and usage'};
export default function Page(){return <AdminRecords section="credits" initialEnvironment={environment()}/>;}
