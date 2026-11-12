import Image from 'next/image';
import Link from 'next/link';
import {
  ArrowUpRight, Bookmark, Building2, Check,
  GraduationCap, Layers3, Plus, ShieldCheck, SlidersHorizontal,
} from 'lucide-react';
import ShortlistPreview from '@/components/shortlist-preview';
import CareerGallery from '@/components/career-gallery';
import WorkflowVisual from '@/components/workflow-visual';
import s from '@/app/landing.module.css';

const workflow = [
  { icon: SlidersHorizontal, title: 'Tell us what you do', copy: 'Share your degree, skills and the kind of work you want to pursue.' },
  { icon: Building2, title: 'Find relevant companies', copy: 'See which UK licensed sponsors do work that overlaps with your background.' },
  { icon: Bookmark, title: 'Make a shortlist', copy: 'Save the companies worth a closer look and check their available contact or application routes.' },
];

const questions = [
  ['Who is SponsorReach for?', 'SponsorReach helps international graduates and professionals research UK licensed sponsor companies based on their skills, experience and career interests.'],
  ['Where does the company information come from?', 'We use sponsor-register information and publicly available company information. A shortlist brings together the company’s work, why it may be relevant to you and available ways to approach it.'],
  ['Does a licence mean a company will sponsor me?', 'A sponsor licence is a starting point for research. Ask the employer about current vacancies and whether they are willing to sponsor the specific role.'],
  ['What contact details will I see?', 'Depending on the company, you may find a website, careers page, published business email, phone number or relevant employee contact supported by the available information.'],
  ['How are research credits used?', 'One credit unlocks a batch of up to 5 companies. Reopening saved results, failed or empty searches, and batches where more than half the companies are already unlocked cost nothing. You can see the credit cost before you continue.'],
  ['What happens to unused credits?', 'Your 5 signup credits are issued once after email verification and have no scheduled expiry. Monthly credits reset each paid billing period. Unused monthly credits expire at the end of that period.'],
];

export default function MarketingHome() {
  return (
    <div className={s.landing}>
      <section className={s.hero} aria-labelledby="landing-title">
        <div className={s.heroCopy}>
          <p className={s.eyebrow}><i/> UK SPONSOR RESEARCH</p>
          <h1 id="landing-title">Find UK<br/> sponsors that<br/> <span>fit your skills.</span></h1>
          <p className={s.heroIntro}>Build a shortlist of licensed employers based on your degree, skills and experience. See why each one fits and where to start your research.</p>
          <div className={s.heroActions}>
            <Link href="/match" className={s.primary}>Start for free <ArrowUpRight size={19}/></Link>
          </div>
          <p className={s.freeNote}><Check size={15}/> 5 free credits when you verify your email</p>
        </div>
        <ShortlistPreview/>
      </section>

      <CareerGallery/>

      <section className={s.workflow} id="how-it-works" aria-labelledby="workflow-title">
        <div className={s.sectionHead}>
          <div><p className={s.eyebrow}><i/> HOW IT WORKS</p><h2 id="workflow-title">From your skills<br/> to a shortlist.</h2></div>
          <p>Start with the work you know. Find companies that do it, then decide which ones are worth approaching.</p>
        </div>
        <ol className={s.steps}>
          {workflow.map(({icon: Icon, title, copy}, index) => <li key={title}>
            <div className={s.stepCopy}>
              <div className={s.stepTop}><span><Icon size={25} strokeWidth={1.65}/></span><span className={s.stepCount}>0{index + 1}</span></div>
              <h3>{title}</h3><p>{copy}</p>
            </div>
            <WorkflowVisual step={index}/>
          </li>)}
        </ol>
      </section>

      <section className={s.evidence} aria-labelledby="evidence-title">
        <div className={s.evidenceInner}>
          <div className={s.evidenceImage}>
            <Image src="/careers/architect.webp" alt="" fill sizes="(max-width: 720px) 90vw, 48vw"/>
            <span className={s.imageLabel}><GraduationCap size={17}/> For international graduates and professionals</span>
          </div>
          <div className={s.evidenceCopy}>
            <p className={s.eyebrow}><i/> INSIDE YOUR SHORTLIST</p>
            <h2 id="evidence-title">Know who to research next.</h2>
            <div className={s.evidenceList}>
              <div><Layers3 size={21}/><p><strong>Company context</strong>What the employer does and where your skills might fit.</p></div>
              <div><ShieldCheck size={21}/><p><strong>Sponsor-register evidence</strong>Licence information and its source date to support your checks.</p></div>
              <div><ArrowUpRight size={21}/><p><strong>Ways to approach</strong>Available careers pages, company websites and published contacts.</p></div>
            </div>
            <Link href="/our-data" className={s.textLink}>Explore our sources <ArrowUpRight size={16}/></Link>
          </div>
        </div>
      </section>

      <section className={s.pricing} id="pricing" aria-labelledby="pricing-title">
        <div className={s.pricingHead}>
          <p className={s.eyebrow}><i/> PRICING</p>
          <h2 id="pricing-title">Start free. Go further when you need to.</h2>
          <p>One research credit unlocks up to 5 companies.</p>
        </div>
        <div className={s.plans}>
          <article className={s.freePlan}>
            <h3>Free signup credits</h3>
            <p className={s.amount}>€0</p>
            <ul><li><Check size={17}/> 5 free credits after email verification</li><li><Check size={17}/> Company context and reasons for relevance</li><li><Check size={17}/> Available application and contact routes</li></ul>
            <Link href="/match" className={s.outlineButton}>Start for free <ArrowUpRight size={17}/></Link>
          </article>
          <article className={s.paidPlan}>
            <h3>SponsorReach Monthly</h3>
            <p className={s.amount}>€24.99 <span>/ month</span></p>
            <ul><li><Check size={17}/> 100 research credits each paid month</li><li><Check size={17}/> The same research and contact features</li><li><Check size={17}/> Manage renewal from your account</li></ul>
            <Link href="/account/billing" className={s.primary}>View subscription <ArrowUpRight size={17}/></Link>
          </article>
        </div>
        <Link href="/refunds" className={s.policyLink}>Payment, cancellation and refund details <ArrowUpRight size={15}/></Link>
      </section>

      <section className={s.faq} id="faq" aria-labelledby="faq-title">
        <div><p className={s.eyebrow}><i/> FAQS</p><h2 id="faq-title">Before you start.</h2><Link href="/contact" className={s.textLink}>Contact us <ArrowUpRight size={16}/></Link></div>
        <div className={s.accordion}>
          {questions.map(([question, answer]) => <details key={question}><summary>{question}<Plus size={19}/></summary><p>{answer}</p></details>)}
        </div>
      </section>

      <section className={s.closing} aria-labelledby="closing-title">
        <div className={s.closingRings} aria-hidden="true"><span/><span/><span/></div>
        <div><h2 id="closing-title">Who could you<br/> work for next?</h2><p>Start with your skills and see where they could take you.</p></div>
        <Link href="/match" className={s.darkButton}>Build my shortlist <ArrowUpRight size={20}/></Link>
      </section>
    </div>
  );
}
