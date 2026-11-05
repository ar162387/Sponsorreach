import {verifiedUser,isAdministrator} from '@/lib/server';
import DashboardShell from '@/components/dashboard-shell';
import AdminLogin from '@/components/admin-login';
export const metadata={robots:{index:false,follow:false}};
export default async function Layout({children}:{children:React.ReactNode}){const user=await verifiedUser();if(!user||!isAdministrator(user))return <AdminLogin/>;return <DashboardShell admin email={user.email||''}>{children}</DashboardShell>;}
