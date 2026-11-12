'use client';

import { useState } from 'react';
import Image from 'next/image';
import { ArrowUpRight, Bookmark, Building2, Check, ChevronRight, GraduationCap, Mail, MapPin, Search, ShieldCheck } from 'lucide-react';
import s from '@/app/landing.module.css';

const matches = [
  { name: 'Northstar Analytics', city: 'Manchester', focus: 'Data & analytics', skill: 'SQL', reason: 'Builds reporting dashboards and maintains the SQL datasets behind them.' },
  { name: 'Meridian Digital', city: 'London', focus: 'Technology consulting', skill: 'Python', reason: 'Uses Python to automate data preparation and reporting on client projects.' },
  { name: 'Kestrel Systems', city: 'Bristol', focus: 'Enterprise software', skill: 'Power BI', reason: 'Builds business dashboards for teams tracking their day-to-day operations.' },
];

function ExampleProfile() {
  return (
    <div className={`${s.stepVisual} ${s.profileVisual}`}>
      <div className={s.profilePortrait}>
        <Image src="/careers/data-analyst.webp" alt="" fill sizes="(max-width: 420px) 92px, 150px"/>
      </div>
      <div className={s.workflowProfile}>
        <span className={s.panelLabel}><GraduationCap size={16}/> Example profile</span>
        <strong>Data analyst</strong>
        <dl><div><dt>Degree</dt><dd>Computer science</dd></div><div><dt>Interests</dt><dd>Reporting & visualisation</dd></div></dl>
        <div className={s.skillLabels}><span>SQL</span><span>Python</span><span>Power BI</span></div>
      </div>
    </div>
  );
}

function EmployerMatches() {
  const [selected, setSelected] = useState(0);
  const match = matches[selected];

  return (
    <div className={`${s.stepVisual} ${s.matchVisual}`}>
      <div className={s.matchWorkspace}>
        <div className={s.matchHeader}><span><Search size={17}/> Research matches</span><span>Data analyst</span></div>
        <div className={s.matchGrid}>
          <div className={s.matchRecords} role="group" aria-label="Example research matches">
            {matches.map(({name, focus}, index) => (
              <button type="button" key={name} aria-pressed={index === selected} onClick={() => setSelected(index)}>
                <Building2 size={15}/><span><strong>{name}</strong><small>{focus}</small></span><ChevronRight size={13}/>
              </button>
            ))}
          </div>
          <div className={s.matchDetail} aria-live="polite" aria-atomic="true">
            <span className={s.panelLabel}><Check size={14}/> Skill match</span>
            <strong>{match.skill}</strong>
            <p>{match.reason}</p>
            <small><MapPin size={13}/> {match.city}</small>
          </div>
        </div>
      </div>
    </div>
  );
}

function ShortlistBoard() {
  const [saved, setSaved] = useState([true, false, false]);
  const savedCount = saved.filter(Boolean).length;

  return (
    <div className={`${s.stepVisual} ${s.saveVisual}`}>
      <div className={s.saveCard}>
        <div className={s.saveHeader}>
          <strong><Bookmark size={17}/> Sample shortlist</strong>
          <span role="status">{savedCount} saved</span>
        </div>
        <div className={s.saveRecords}>
          {matches.map(({name, city}, index) => (
            <div className={s.saveRow} key={name}>
              <span className={s.saveCompanyIcon}><Building2 size={16}/></span>
              <div><strong>{name}</strong><small>{city}</small></div>
              <button type="button" aria-label={`Save ${name}`} aria-pressed={saved[index]}
                onClick={() => setSaved(current => current.map((value, position) => position === index ? !value : value))}>
                <Bookmark size={16} fill={saved[index] ? 'currentColor' : 'none'}/>
              </button>
            </div>
          ))}
        </div>
        <div className={s.saveCardRoutes}><span><Mail size={14}/> Email</span><span><ArrowUpRight size={14}/> Careers page</span><span><ShieldCheck size={14}/> Sponsor record</span></div>
      </div>
    </div>
  );
}

export default function WorkflowVisual({step}: {step: number}) {
  if (step === 0) return <ExampleProfile/>;
  if (step === 1) return <EmployerMatches/>;
  return <ShortlistBoard/>;
}
