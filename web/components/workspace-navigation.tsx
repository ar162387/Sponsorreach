'use client';
import {createContext,useContext,useMemo,type ReactNode} from 'react';
import {useRouter} from 'next/navigation';
const paths={account:new Set(['/account','/account/search','/account/shortlists','/account/saved','/account/billing','/account/support']),admin:new Set(['/admin','/admin/members','/admin/payments','/admin/refunds','/admin/credits','/admin/reconciliation','/admin/support'])};
export const NEW_SEARCH_REQUESTED='sponsorreach:new-search';
const Context=createContext<'account'|'admin'|null>(null);
export function WorkspaceNavigation({admin=false,children}:{admin?:boolean;children:ReactNode}){return <Context.Provider value={admin?'admin':'account'}>{children}</Context.Provider>;}
export function useWorkspaceRouter(){
 const router=useRouter(),scope=useContext(Context);
 return useMemo(()=>{
  function destination(href:string){if(!scope||!href.startsWith('/')||href.startsWith('//'))return null;const url=new URL(href,'https://workspace.invalid');if(!paths[scope].has(url.pathname))return null;
   if(url.pathname==='/account'&&url.searchParams.get('new')==='1'){url.pathname='/account/search';url.searchParams.delete('new');}
   if(url.pathname==='/account'&&url.searchParams.has('shortlist'))url.pathname='/account/shortlists';
   return url.pathname+url.search+url.hash;
  }
  function navigate(href:string,replace=false,scroll=true){const target=destination(href);if(target===null){if(replace)router.replace(href,{scroll});else router.push(href,{scroll});return;}
   if(target==='/account/search'&&location.pathname==='/account/search'&&!location.search)window.dispatchEvent(new Event(NEW_SEARCH_REQUESTED));
   if(replace)window.history.replaceState(null,'',target);else window.history.pushState(null,'',target);
   if(scroll)window.scrollTo({top:0,behavior:'instant'});
  }
  return {...router,canNavigate:(href:string)=>destination(href)!==null,push:(href:string,options?:{scroll?:boolean})=>navigate(href,false,options?.scroll!==false),replace:(href:string,options?:{scroll?:boolean})=>navigate(href,true,options?.scroll!==false)};
 },[router,scope]);
}
