import SiteChrome, { SiteMain } from '@/components/site-chrome';
import { PublicFooter, PublicHeader } from '@/components/public-chrome';
import type { Metadata } from 'next';
import { verifiedUser } from '@/lib/server';
import './globals.css';
import './internal-theme.css';
import './dashboard.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.APP_ORIGIN || 'https://sponsorreach.uk'),
  title: { default: 'UK Sponsor Company Research for Graduates | SponsorReach', template: '%s | SponsorReach UK' },
  description: 'Find UK licensed sponsor companies relevant to your degree, skills and goals. Build a personal shortlist and contact employers through available email, phone and application routes.',
  openGraph: { title: 'Find UK sponsor companies that fit your skills.', description: 'Research UK licensed sponsor companies matched to your skills. €24.99/month.', siteName: 'SponsorReach UK', locale: 'en_GB', type: 'website' },
  twitter: { card: 'summary', title: 'SponsorReach UK', description: 'Research UK licensed sponsor companies matched to your skills. €24.99/month.' },
  icons: { icon: [{ url: '/icon.svg?v=3', sizes: 'any', type: 'image/svg+xml' }], shortcut: '/icon.svg?v=3', apple: '/apple-icon.png' },
};
export const dynamic = 'force-dynamic';
export default async function Layout({ children }: { children: React.ReactNode }) {
  const user=await verifiedUser();
  return <html lang="en-GB" data-scroll-behavior="smooth"><body className={user?'authenticated-app':undefined}>
    <a className="skip" href="#main">Skip to content</a>
    <SiteChrome signedIn={!!user}><PublicHeader signedIn={!!user}/></SiteChrome>
    <SiteMain signedIn={!!user}>{children}</SiteMain>
    <SiteChrome signedIn={!!user}><PublicFooter signedIn={!!user}/></SiteChrome>
  </body></html>;
}
