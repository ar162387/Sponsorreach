import Image from 'next/image';
import Link from 'next/link';
import { SigninLink } from '@/components/signin-dialog';
import { ArrowUpRight, ChevronDown } from 'lucide-react';
import AccountNav from '@/components/account-nav';
import AgentaBadge from '@/components/agenta-badge';
import s from '@/app/landing.module.css';

const footerLinks = [
  ['Product', [
    ['Build a shortlist', '/match'], ['My shortlists', '/account'], ['Pricing', '#pricing'], ['Our data', '/our-data'],
  ]],
  ['Support', [
    ['Contact', '/contact'], ['Payments & refunds', '/refunds'], ['Disclaimer', '/disclaimer'],
  ]],
  ['Legal', [
    ['Terms', '/terms'], ['Privacy', '/privacy'], ['Data deletion', '/data-deletion'],
  ]],
] as const;

function Wordmark() {
  return (
    <Link className={s.identity} href="/" aria-label="SponsorReach UK home">
      <span className={s.brandMark}><Image src="/brand/sr-mark-navy.png" width={24} height={14} alt=""/></span>
      <span>SponsorReach<span className={s.brandCountry}> UK</span></span>
    </Link>
  );
}

export function PublicHeader({signedIn}: {signedIn: boolean}) {
  const home = signedIn ? '/about' : '/';
  return (
    <header className={s.masthead}>
      <div className={s.navInner}>
        <Wordmark/>
        <nav className={s.mainNav} aria-label="Landing navigation">
          <Link href={home + "#how-it-works"}>How it works</Link><Link href={home + "#pricing"}>Pricing</Link><Link href={home + "#faq"}>FAQs</Link>
        </nav>
        <div className={s.navActions}>
          {signedIn ? <AccountNav signedIn/> : <>
            <SigninLink className={s.signIn}>Sign in</SigninLink>
            <SigninLink className={s.navCta} destination="/account/search">Start for free <ArrowUpRight size={15}/></SigninLink>
          </>}
        </div>
        <details className={s.mobileMenu}>
          <summary>Menu <ChevronDown size={14}/></summary>
          <nav aria-label="Mobile landing navigation">
            <Link href={home + "#how-it-works"}>How it works</Link><Link href={home + "#pricing"}>Pricing</Link><Link href={home + "#faq"}>FAQs</Link><SigninLink>{signedIn ? "My account" : "Sign in"}</SigninLink>{!signedIn && <SigninLink destination="/account/search" className={s.navCta}>Start for free <ArrowUpRight size={15}/></SigninLink>}
          </nav>
        </details>
      </div>
    </header>
  );
}

export function PublicFooter({signedIn}: {signedIn: boolean}) {
  const home = signedIn ? '/about' : '/';
  return (
    <footer className={s.footer}>
      <div className={s.footerGrid}>
        <div><Wordmark/><p>UK employer research for international graduates and professionals.</p><AgentaBadge/></div>
        {footerLinks.map(([group, links]) => <nav key={group} aria-label={group}><h2>{group}</h2>{links.map(([label, href]) => href === '/match' || href === '/account'
          ? <SigninLink key={href} destination={href === '/match' ? '/account/search' : '/account'}>{label}</SigninLink>
          : <Link key={href} href={href.startsWith("#") ? home + href : href}>{label}</Link>)}</nav>)}
      </div>
      <div className={s.footerBottom}>
        <p>Employers decide whether to offer a job or sponsorship.</p>
        <nav className={s.socialLinks} aria-label="Social media">
          <a href="https://www.instagram.com/sponsorreach/" aria-label="Instagram" target="_blank" rel="noopener noreferrer">
            <svg aria-hidden="true" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
              <rect x="3" y="3" width="18" height="18" rx="5"/>
              <circle cx="12" cy="12" r="4"/>
              <circle cx="17.5" cy="6.6" r="1" fill="currentColor" stroke="none"/>
            </svg>
          </a>
          <a href="https://www.linkedin.com/company/145280669/" aria-label="LinkedIn" target="_blank" rel="noopener noreferrer">
            <svg aria-hidden="true" width="19" height="19" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.5 3h-17C2.7 3 2 3.7 2 4.5v15C2 20.3 2.7 21 3.5 21h17c.8 0 1.5-.7 1.5-1.5v-15C22 3.7 21.3 3 20.5 3ZM8 18H5V9.5h3V18ZM6.5 8.2a1.6 1.6 0 1 1 0-3.2 1.6 1.6 0 0 1 0 3.2ZM19 18h-3v-4.2c0-1-.4-1.6-1.3-1.6s-1.7.6-1.7 1.6V18h-3V9.5h3v1.1a3 3 0 0 1 2.5-1.3c2 0 3.5 1.1 3.5 3.8V18Z"/>
            </svg>
          </a>
        </nav>
      </div>
    </footer>
  );
}
