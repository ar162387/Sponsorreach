'use client';

import { useState } from 'react';
import { BriefcaseBusiness, Building2, Check, ChevronRight, Code2, Compass, Globe2, HeartPulse, Mail, MapPin, Phone, Search, Wrench } from 'lucide-react';
import s from '@/app/landing.module.css';

const profiles = [
  {
    label: 'Technology', icon: Code2, role: 'Data analyst', skills: 'SQL · Python · Power BI',
    companies: [
      { name: 'Northstar Analytics', city: 'Manchester', field: 'Data & analytics', reason: 'Builds reports with SQL and Power BI.', domain: 'northstar.example', phone: '+44 161 496 0104', boards: 'LinkedIn · Indeed' },
      { name: 'Meridian Digital', city: 'London', field: 'Technology consulting', reason: 'Uses Python in client analytics projects.', domain: 'meridian.example', phone: '+44 20 7946 0341', boards: 'LinkedIn · Totaljobs' },
      { name: 'Kestrel Systems', city: 'Bristol', field: 'Enterprise software', reason: 'Builds dashboards using business data.', domain: 'kestrel.example', phone: '+44 117 496 0182', boards: 'Indeed · TechJobs' },
    ],
  },
  {
    label: 'Engineering', icon: Wrench, role: 'Mechanical engineer', skills: 'CAD · Prototyping · FEA',
    companies: [
      { name: 'Alder Engineering', city: 'Birmingham', field: 'Mechanical design', reason: 'Uses CAD and prototyping for product design.', domain: 'alder.example', phone: '+44 121 496 0160', boards: 'Indeed · Totaljobs' },
      { name: 'Hawthorn Dynamics', city: 'Derby', field: 'Advanced manufacturing', reason: 'Uses finite element analysis to test parts.', domain: 'hawthorn.example', phone: '+44 1632 960081', boards: 'LinkedIn · Indeed' },
      { name: 'Westmere Projects', city: 'Glasgow', field: 'Engineering consultancy', reason: 'Models and reviews industrial designs.', domain: 'westmere.example', phone: '+44 141 496 0192', boards: 'LinkedIn · Totaljobs' },
    ],
  },
  {
    label: 'Healthcare', icon: HeartPulse, role: 'Registered nurse', skills: 'Acute care · Triage',
    companies: [
      { name: 'Ashford Care Group', city: 'Leeds', field: 'Hospital services', reason: 'Runs acute care and triage services.', domain: 'ashford.example', phone: '+44 113 496 0141', boards: 'Indeed · Totaljobs' },
      { name: 'Willow Health', city: 'Nottingham', field: 'Community care', reason: 'Assesses patients and plans community care.', domain: 'willow.example', phone: '+44 115 496 0184', boards: 'LinkedIn · Indeed' },
      { name: 'Bridgewell Health', city: 'Liverpool', field: 'Clinical services', reason: 'Provides patient monitoring and care planning.', domain: 'bridgewell.example', phone: '+44 151 496 0116', boards: 'Indeed · Totaljobs' },
    ],
  },
];

export default function ShortlistPreview() {
  const [profileIndex, setProfileIndex] = useState(0);
  const [companyIndex, setCompanyIndex] = useState(0);
  const profile = profiles[profileIndex];
  const company = profile.companies[companyIndex];
  const routes = [
    { icon: Mail, label: 'Email', value: 'jobs@' + company.domain },
    { icon: Phone, label: 'Phone', value: company.phone },
    { icon: Globe2, label: 'Website', value: company.domain },
    { icon: BriefcaseBusiness, label: 'Job boards', value: company.boards },
  ];

  return (
    <figure className={s.preview} id="preview" aria-label="Shortlist example with sample contact information">
      <div className={s.previewBackdrop} aria-hidden="true"><span/><span/><span/></div>
      <div className={s.previewTop}>
        <span><Compass size={17}/> Shortlist explorer</span>
      </div>
      <div className={s.previewBody}>
        <div className={s.profilePicker} role="group" aria-label="Choose an example field">
          {profiles.map(({label, icon: Icon}, index) => (
            <button key={label} type="button" aria-pressed={profileIndex === index} onClick={() => { setProfileIndex(index); setCompanyIndex(0); }}>
              <Icon size={15}/>{label}
            </button>
          ))}
        </div>
        <div className={s.demoProfile}>
          <span className={s.demoSearchIcon}><Search size={17}/></span>
          <div><strong>{profile.role}</strong><small>{profile.skills}</small></div>
          <span className={s.sampleCount}>Example profile</span>
        </div>
        <div className={s.companyGrid}>
          <div className={s.demoCompanies} role="group" aria-label="Choose an example employer">
            {profile.companies.map((item, index) => (
              <button key={item.name} type="button" aria-pressed={companyIndex === index} onClick={() => setCompanyIndex(index)}>
                <span className={s.companyMark}><Building2 size={15}/></span>
                <span><strong>{item.name}</strong><small>{item.city}</small></span>
                <ChevronRight className={s.companyArrow} size={14}/>
              </button>
            ))}
          </div>
          <div className={s.companyDetail} aria-live="polite" aria-atomic="true">
            <div key={company.name} className={s.detailContent}>
              <span className={s.matchLabel}><Check size={13}/> Why it fits</span>
              <strong>{company.name}</strong>
              <span className={s.demoLocation}><MapPin size={12}/> {company.city} · {company.field}</span>
              <p>{company.reason}</p>
                <dl className={s.contactStrip} aria-label="Sample contact routes">
                  {routes.map(({icon: Icon, label, value}) => (
                    <div key={label}><dt><Icon size={13}/> <span>{label}</span></dt><dd>{value}</dd></div>
                  ))}
                </dl>
            </div>
          </div>
        </div>
      </div>
    </figure>
  );
}
