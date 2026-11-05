import {verifiedUser,isAdministrator} from '@/lib/server';
import DashboardShell from '@/components/dashboard-shell';
import MemberWorkspace from '@/components/member-workspace';
export default async function Layout({children}:{children:React.ReactNode}){const user=await verifiedUser();if(!user)return children;return <DashboardShell email={user.email||''} isAdmin={isAdministrator(user)}><MemberWorkspace>{children}</MemberWorkspace></DashboardShell>;}
