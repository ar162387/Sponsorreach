'use client';
import {usePathname} from 'next/navigation';
import AdminRecords,{AdminOverview} from './admin-dashboard';
import SupportConsole from './support-console';
export default function AdminWorkspace({children,environment}:{children:React.ReactNode;environment:string}){
 const path=usePathname(),section=path.split('/')[2];
 if(path==='/admin')return <AdminOverview/>;
 if(section==='support')return <SupportConsole admin supportOnly/>;
 if(['members','payments','refunds','credits','reconciliation'].includes(section))return <AdminRecords key={section} section={section} initialEnvironment={environment}/>;
 return <>{children}</>;
}
