import SiteChrome from '@/components/site-chrome';
import AgentaBadge from '@/components/agenta-badge';
import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import AccountNav from '@/components/account-nav';
import {verifiedUser} from '@/lib/server';

import Brand from '@/components/brand';
import './globals.css';
import './internal-theme.css';
import './dashboard.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.APP_ORIGIN || 'https://sponsorreach.uk'),
  title: { default: 'UK Sponsor Company Research for Graduates | SponsorReach', template: '%s | SponsorReach UK' },
  description: 'Find UK licensed sponsor companies relevant to your degree, skills and goals. Build a personal shortlist and contact employers through available email, phone and application routes.',
  openGraph: { title: 'Find UK sponsor companies that fit your skills.', description: 'Research UK licensed sponsor companies matched to your skills. US$24.99/month.', siteName: 'SponsorReach UK', locale: 'en_GB', type: 'website' },
  twitter: { card: 'summary', title: 'SponsorReach UK', description: 'Research UK licensed sponsor companies matched to your skills. US$24.99/month.' },
  icons: { icon: [{ url: '/icon.svg?v=3', sizes: 'any', type: 'image/svg+xml' }], shortcut: '/icon.svg?v=3', apple: '/apple-icon.png' },
};
export const dynamic = 'force-dynamic';
export default async function Layout({ children }: { children: React.ReactNode }) {
  const user=await verifiedUser();
  return <html lang="en-GB"><body className={user?'authenticated-app':undefined}>
    <a className="skip" href="#main">Skip to content</a>
    <SiteChrome signedIn={!!user}><header className="header"><Brand/><AccountNav signedIn={!!user}/></header></SiteChrome>
    <main id="main" tabIndex={-1}>{children}</main>
    <SiteChrome signedIn={!!user}><footer className="footer"><div className="footer-main"><Brand/><p>Personalised employer research<br/>for international graduates.</p></div><div className="footer-links"><Link href="/match">Build my shortlist</Link><Link href="/account">My sponsor shortlists</Link><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/our-data">Our data</Link><Link href="/disclaimer">Disclaimer</Link><Link href="/contact">Contact</Link><Link href="/refunds">Payments &amp; refunds</Link></div><p className="footer-note">SponsorReach UK helps you research licensed sponsors and contact relevant companies. Employers decide whether to offer a job and sponsorship.</p><div style={{marginTop:24}}><AgentaBadge/></div></footer></SiteChrome>
  </body></html>;
}
