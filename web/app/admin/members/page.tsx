import AdminRecords from '@/components/admin-dashboard';
import {environment} from '@/lib/billing-server';
export const metadata={title:'Members'};
export default function Page(){return <AdminRecords section="members" initialEnvironment={environment()}/>;}
