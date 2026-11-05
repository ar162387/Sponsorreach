import AdminRecords from '@/components/admin-dashboard';
import {environment} from '@/lib/billing-server';
export const metadata={title:'Payments'};
export default function Page(){return <AdminRecords section="payments" initialEnvironment={environment()}/>;}
