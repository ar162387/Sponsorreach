import type {ReactNode} from 'react';
export function DataValue({loading,children,label='value'}:{loading:boolean;children:ReactNode;label?:string}){return loading?<span className="data-placeholder" role="status" aria-label={'Loading '+label}><span aria-hidden="true">&nbsp;</span></span>:<>{children}</>;}
export function DataRows({label='records'}:{label?:string}){return <div className="data-rows" role="status" aria-label={'Loading '+label}>{[0,1,2].map(i=><span key={i} className="data-placeholder" aria-hidden="true">&nbsp;</span>)}</div>;}
