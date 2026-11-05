import Account from '@/components/account';
import MemberOverview from '@/components/member-overview';
import {verifiedUser} from '@/lib/server';
import {redirect} from 'next/navigation';
export const metadata={title:'Your workspace',robots:{index:false,follow:false}};
export default async function Page({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}){const user=await verifiedUser();if(!user)return <Account/>;const params=await searchParams;if(params.new==='1')redirect('/account/search');if(typeof params.shortlist==='string')redirect('/account/shortlists?'+new URLSearchParams({shortlist:params.shortlist,...(params.edit==='1'?{edit:'1'}:{})}));return <MemberOverview/>;}
