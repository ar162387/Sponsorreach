import CareerGallery from '@/components/career-gallery';
import AgentaBadge from '@/components/agenta-badge';
import Link from 'next/link';
import Image from 'next/image';
import LandingMotion from '@/components/landing-motion';
import { ArrowUpRight, ArrowRight, Asterisk, GraduationCap, Code2, Building2, BriefcaseBusiness } from 'lucide-react';
import s from '@/app/landing.module.css';

const questions = [
  ['What does SponsorReach help me do?', 'Research UK licensed sponsor companies whose work connects with your background. Your shortlist brings together company context, reasons for relevance and available contact or application routes. You decide which companies to investigate and approach.'],
  ['Why not just use the public register?', 'The register identifies licensed organisations. SponsorReach adds professional relevance, supporting company context and available ways to approach them, organised around the background you provide.'],
  ['Does a licence mean a company will sponsor me?', 'No. A licence does not establish a current vacancy, willingness to sponsor your role or an offer. Check each opportunity directly with the employer.'],
  ['Will I get a contact for every company?', 'Available routes vary websites, careers pages, published emails, phone numbers and other business links. Relevant employee contacts appear only when supported by the available information. A contact does not guarantee a reply.'],
  ['What can I access right now?', 'Start with 10 free credits when you sign up. Subscribe when you need more.'],
];

export const dynamic="force-dynamic";
export default async function MarketingHome() {
  const faqs=questions.map(([q,a])=>[q,q==="What can I access right now?"?"Sign up and verify your email to receive 10 free research credits. Each search or new results batch uses one credit when results are delivered. Once your free credits are used, subscribe for US$24.99 per month for 800 credits. Failed or empty searches and reopening saved results use no credits.":a]);
  return <div className={s.landing} data-atlas-landing="true">
    <header className={s.masthead}>
      <Link className={s.identity} href="/" aria-label="SponsorReach UK home"><Image src="/brand/sr-mark.png" alt="" width={48} height={28} priority className={s.logoMark}/><span>SponsorReach<sup>UK</sup></span></Link>
      <nav aria-label="Landing navigation"><a href="#how-it-works">How it works</a><a href="#pricing">Pricing</a><a href="#faq">FAQs</a><Link href="/account">My shortlists <ArrowUpRight size={14}/></Link></nav>
    </header>

    <section className={s.opening} aria-labelledby="landing-title">
      <h1 id="landing-title" data-atlas-reveal data-atlas-delay="60">Connect with UK licensed sponsor companies<br/>that fit <em>your skills.</em></h1>
      <p className={s.intro} data-atlas-reveal data-atlas-delay="120">Research UK licensed sponsor companies relevant to your degree, skills and experience. Built for international graduates and professionals who want a focused employer shortlist, company evidence and practical ways to make an approach.</p>
      <Link href="/match" className={s.primary}>Start for free <ArrowUpRight size={20}/></Link>
      <LandingMotion/>
      <span className={s.bubbleFour} aria-hidden="true"/><span className={s.bubbleFive} aria-hidden="true"/><span className={s.bubbleSix} aria-hidden="true"/><span className={s.bubbleSeven} aria-hidden="true"/><span className={s.bubbleEight} aria-hidden="true"/><span className={s.bubbleOne} aria-hidden="true"/><span className={s.bubbleTwo} aria-hidden="true"/><span className={s.bubbleThree} aria-hidden="true"/><span className={s.orbitOne} aria-hidden="true"/><span className={s.orbitTwo} aria-hidden="true"/>
    </section>

    <section className={s.thread} id="how-it-works" aria-labelledby="thread-title">
      <div className={s.chapter}><span>01 / THE APPROACH</span><span>A SHORTER PATH THROUGH THE NOISE</span></div>
      <h2 id="thread-title" data-atlas-reveal>A list gives you names.<br/><em>Context gives you direction.</em></h2>
      <p className={s.sectionIntro}>Start with what you know. Explore where it could fit.<br/>Then decide who is worth your time.</p>
      <div className={s.fitGraphic} aria-label="From your background to employer research and your career goal"><div className={s.profileSketch}><GraduationCap size={25}/><span>YOUR STARTING POINT</span><strong>A direction of your own</strong><p>Your degree, skills and the work you want to do.</p><div><span><Code2 size={15}/>Your skills</span><span>Your experience</span><span>Your interests</span></div></div><div className={s.fitPath} aria-hidden="true"><span/><ArrowRight size={28}/><span/></div><div className={s.companySketch}><span>YOUR RESEARCH</span><div><Building2 size={23}/><span><strong>Relevant companies</strong><small>What each business does and why it may fit your background.</small></span></div><div><BriefcaseBusiness size={23}/><span><strong>A focused shortlist</strong><small>Company websites, careers pages and published business contacts.</small></span></div><small>Choose who to research and approach.</small></div><div className={s.fitPath} aria-hidden="true"><span/><ArrowRight size={28}/><span/></div><div className={s.outcomeSketch}><ArrowUpRight size={29}/><span>THE GOAL</span><strong>Your next career chapter</strong><p>Work toward a sponsored role that fits your skills and ambitions.</p></div></div>
    </section>

    <section className={s.fieldnotes} aria-labelledby="evidence-title"><div className={s.chapter}><span>RESEARCH YOU CAN INTERPRET</span><span>FROM BACKGROUND TO NEXT STEP</span></div><h2 id="evidence-title">See what each signal<br/><em>actually tells you.</em></h2><div className={s.signalGrid}><article><span className={s.annotation}>01 / REGISTER</span><h3>Licensed sponsor</h3><p>Use sponsor-register information and its source date as a starting point. A licence does not confirm a current sponsored vacancy.</p></article><article><span className={s.annotation}>02 / RELEVANCE</span><h3>Professional fit</h3><p>Company activities connect with the background you provide. A recommendation is a research lead, not an assessment of visa eligibility.</p></article><article><span className={s.annotation}>03 / ACTION</span><h3>Verify and approach</h3><p>Check the employer’s careers page and current requirements. Apply directly or make a relevant approach through an available business route.</p></article></div><p><Link href="/our-data">Read about our sources and limitations ↗</Link></p></section>

    <section className={s.fieldnotes} aria-labelledby="notes-title">
      <div className={s.chapter}><span>02 / INSIDE YOUR SHORTLIST</span><span>INFORMATION WITH A PURPOSE</span></div>
      <div className={s.notesHeading} data-atlas-reveal><h2 id="notes-title">Know a little more.<br/><em>Approach a little better.</em></h2><p>Something more useful than a company name.<br/>Something you can take your next step with.</p></div>
      <div className={s.indexRow} data-atlas-reveal="row"><span className={s.indexNumber} data-atlas-accent="number">I.</span><h3>The work behind the name</h3><p>Company context to help you understand what a business does and where your interests could connect.</p><span className={s.marginNote}>COMPANY CONTEXT</span></div>
      <div className={s.indexRow} data-atlas-reveal="row"><span className={s.indexNumber} data-atlas-accent="number">II.</span><h3>A reason to consider it</h3><p>See why company activities may fit your background. Research with a rationale, rather than a list to work through blindly.</p><span className={s.marginNote}>PROFESSIONAL RELEVANCE</span></div>
      <div className={s.indexRow} data-atlas-reveal="row"><span className={s.indexNumber} data-atlas-accent="number">III.</span><h3>A place to begin</h3><p>Available websites, careers pages and published business contacts. Relevant employee contacts appear when supported by the information available.</p><span className={s.marginNote}>AVAILABLE ROUTES</span></div>
      <div className={s.evidenceNote} data-atlas-reveal><Asterisk size={28}/><p><strong>A licence is a starting point.</strong> Sponsor-register information and its source date help you research a company. They do not confirm an open role or willingness to sponsor you.</p></div>
    </section>

    <CareerGallery/>

    <section className={s.fieldnotes} id="pricing" aria-labelledby="pricing-title">
      <div className={s.chapter}><span>03 / SIMPLE MONTHLY PRICING</span><span>ONE SUBSCRIPTION</span></div>
      <div className={s.priceCard}><div><p className={s.annotation}>SPONSORREACH MONTHLY</p><h2 id="pricing-title">A focused search.<br/><em>One clear price.</em></h2><p className={s.price}>US$24.99 <span>/ month</span></p><p>800 research credits each paid month.</p><Link href="/account/billing" className={s.primary}>View subscription <ArrowUpRight size={20}/></Link></div><div><h3>What your subscription includes</h3><ul><li>Employer research matched to your professional background</li><li>Company context and reasons for relevance</li><li>Available careers pages and published business contacts</li><li>Saved shortlists, billing history and receipts</li></ul><Link href="/refunds">Payment, cancellation and refund details ↗</Link></div></div>
    </section>
    <section className={s.questions} id="faq" aria-labelledby="faq-title">
      <div className={s.chapter}><span>03 / BEFORE YOU BEGIN</span><span>A FEW STRAIGHT ANSWERS</span></div>
      <div className={s.questionLayout}><div><h2 id="faq-title" data-atlas-reveal>Good questions.<br/><em>Clear answers.</em></h2><p>Your shortlist supports your research.<br/>The next decision stays with you.</p><Link href="/terms">Read the terms <ArrowUpRight size={16}/></Link></div><div className={s.accordion}>{faqs.map(([q,a],i)=><details key={q} data-atlas-reveal="row"><summary><span className={s.questionNumber}>0{i+1}</span>{q}<span className={s.plus} aria-hidden="true">+</span></summary><p>{a}</p></details>)}</div></div>
    </section>

    <section className={s.invitation} aria-labelledby="invitation-title"><span className={s.invitationStar} data-atlas-reveal="turn" aria-hidden="true"><Asterisk size={70} strokeWidth={1}/></span><p className={s.kicker}>FOR THE WORK YOU WANT TO DO NEXT</p><h2 id="invitation-title" data-atlas-reveal>There’s a company<br/>worth <em>looking into.</em></h2><p>Start with your skills. See where the research takes you.</p><Link href="/match" className={s.primary}>Start for free <ArrowUpRight size={20}/></Link><small>10 free credits to get started. More research when you need it.</small></section>
    <footer className={s.footer}><div className={s.footerTop}><Link href="/" className={s.footerName}>SponsorReach<span>UK</span></Link><p>Useful research.<br/>An approach of your own.</p></div><div className={s.footerContact}><nav aria-label="Social media"><a href="https://www.instagram.com/sponsorreach/" target="_blank" rel="noopener noreferrer">Instagram <ArrowUpRight size={14}/></a><a href="https://www.linkedin.com/company/145280669/" target="_blank" rel="noopener noreferrer">LinkedIn <ArrowUpRight size={14}/></a></nav><p>For business enquiries: <a href="mailto:info@sponsorreach.uk">info@sponsorreach.uk</a></p></div><div className={s.footerBottom}><p>Company research for international graduates.<br/>No employment, response or sponsorship outcome is guaranteed.</p><nav aria-label="Footer navigation"><Link href="/account">My shortlists</Link><Link href="/contact">Contact</Link><Link href="/terms">Terms</Link><Link href="/privacy">Privacy</Link><Link href="/our-data">Our data</Link><Link href="/disclaimer">Disclaimer</Link><Link href="/refunds">Payments &amp; refunds</Link></nav></div><div style={{marginTop:24}}><AgentaBadge/></div></footer>
  </div>;
}
