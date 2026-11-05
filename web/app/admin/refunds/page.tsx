import AdminRecords from '@/components/admin-dashboard';
import {environment} from '@/lib/billing-server';
export const metadata={title:'Refunds'};
export default function Page(){return <AdminRecords section="refunds" initialEnvironment={environment()}/>;}
