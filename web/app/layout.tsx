import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import Brand from '@/components/brand';
import AccountNav from '@/components/account-nav';
import { verifiedUser } from '@/lib/server';
import { APPLICATIONS_CLOSED_MESSAGE } from '@/lib/applications';
import './globals.css';

// Runtime auth configuration must never freeze a guest header into the build.
export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.APP_ORIGIN || 'http://127.0.0.1:3000'),
  title: { default: 'SponsorReach UK — Find UK sponsors before your PSW runs out', template: '%s | SponsorReach UK' },
  description: 'Find UK licensed sponsor companies relevant to your degree, skills and goals. Build a personal shortlist and contact employers through available email, phone and application routes.',
  openGraph: { title: 'SponsorReach UK — Your skills. Your sponsor shortlist.', description: 'Make your next move count. Discover relevant UK licensed sponsors and available ways to reach them directly.', siteName: 'SponsorReach UK', locale: 'en_GB', type: 'website', images: [{ url: '/brand/social-share.png', width: 1200, height: 630, alt: 'SponsorReach UK — Find relevant UK sponsors. Reach out directly.' }] },
  twitter: { card: 'summary_large_image', title: 'SponsorReach UK', description: 'Find relevant UK licensed sponsors and reach out directly.', images: ['/brand/social-share.png'] },
  icons: { icon: [{ url: '/icon.png', sizes: '64x64', type: 'image/png' }], apple: '/apple-icon.png' },
};
export default async function Layout({ children }: { children: React.ReactNode }) {
  const user = await verifiedUser();
  return <html lang="en-GB"><body className={user ? 'authenticated-app' : undefined}>
    <a className="skip" href="#main">Skip to content</a>
    <header className="header"><Brand/><AccountNav signedIn={!!user}/></header>
    <aside className="applications-notice" aria-label="Application status">{APPLICATIONS_CLOSED_MESSAGE}</aside>
    <main id="main" tabIndex={-1}>{children}</main>
    <footer className="footer"><div className="footer-main"><Brand inverse/><p>Relevant UK sponsors.<br/>A clearer way to reach them.</p></div><div className="footer-links"><Link href="/match">Find my sponsors</Link><Link href="/account">My sponsor shortlists</Link><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link></div><p className="footer-note">SponsorReach UK helps you research licensed sponsors and contact relevant companies. Employers decide whether to offer a job and sponsorship.</p></footer>
  </body></html>;
}
