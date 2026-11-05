import AdminRecords from '@/components/admin-dashboard';
import {environment} from '@/lib/billing-server';
export const metadata={title:'Reconciliation'};
export default function Page(){return <AdminRecords section="reconciliation" initialEnvironment={environment()}/>;}
