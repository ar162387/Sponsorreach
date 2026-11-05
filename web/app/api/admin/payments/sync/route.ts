import {NextResponse} from 'next/server';
import {account,reconcile,BillingError} from '@/lib/billing-server';
import {sameOrigin} from '@/lib/server';
export async function POST(request:Request){try{if(!sameOrigin(request))throw new BillingError('Invalid origin',403);const actor=await account(true);return NextResponse.json(await reconcile('manual',actor.id),{headers:{'Cache-Control':'private, no-store'}});}catch(e){return NextResponse.json({error:e instanceof BillingError?e.message:'Provider synchronisation failed; pending work remains queued'},{status:e instanceof BillingError?e.status:503});}}
