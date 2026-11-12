'use client';

import {useState} from 'react';
import type {LocationMode, Profile, ProfessionChoice} from '@/lib/types';

const split = (value: string) => [...new Set(value.split(',').map(part => part.trim()).filter(Boolean))];

export default function ShortlistFilters({profile, creditMode, onRefine, choices, error}: {
  profile: Profile;
  creditMode?: boolean;
  choices: ProfessionChoice[];
  error: string;
  onRefine: (profile: Profile) => void;
}) {
  const originalBackground = [profile.background.subject,profile.background.specialization].filter(Boolean).join(' · ');
  const [background, setBackground] = useState(originalBackground);
  const [roles, setRoles] = useState(profile.role_intents.map(role => role.raw_label).join(', '));
  const [skills, setSkills] = useState(profile.skills.map(skill => skill.label).join(', '));
  const [industries, setIndustries] = useState(profile.preferred_industries.join(', '));
  const [location, setLocation] = useState(profile.location.preferred_regions.join(', '));
  const [mode, setMode] = useState<LocationMode>(profile.location.mode ?? (
    profile.location.relocate || !profile.location.preferred_regions.length ? 'anywhere' : profile.location.strict ? 'selected_area' : 'prefer_area'
  ));
  const [related, setRelated] = useState(profile.related_roles_enabled);
  const [concepts,setConcepts] = useState<Record<number,string>>({});
  const [validation, setValidation] = useState('');
  function submit(event: React.FormEvent) {
    event.preventDefault();
    const labels = split(roles);
    const skillLabels = split(skills);
    const regions = split(location);
    const sectors = split(industries);
    if(background.trim()!==originalBackground&&background.trim().length>180){
      setValidation('Keep the background under 181 characters.');
      return;
    }
    if (!labels.length || labels.length > 3 || labels.some(label => label.length < 2 || label.length > 120)) {
      setValidation('Enter one to three roles, separated by commas.');
      return;
    }
    if (skillLabels.length > 20 || skillLabels.some(label=>label.length>100) || regions.length > 5 || sectors.length > 5 || (mode !== 'anywhere' && !regions.length)) {
      setValidation('Enter up to 20 skills, five locations and five industries. Area searches need at least one location.');
      return;
    }
    setValidation('');
    const keepConcept = background.trim() === originalBackground && skills === profile.skills.map(skill => skill.label).join(', ');
    onRefine({
      ...profile,
      background: background.trim()===originalBackground ? profile.background : {subject:background.trim(),specialization:''},
      role_intents: labels.map((raw_label,index) => ({
        raw_label, confirmed: true, concept_id: concepts[index] || (keepConcept ? profile.role_intents.find(role => role.raw_label === raw_label)?.concept_id : null),
      })),
      skills: skillLabels.map(label => profile.skills.find(skill => skill.label === label) ?? {label, source: 'user'}),
      preferred_industries: sectors,
      location: {...profile.location, mode, preferred_regions: regions},
      related_roles_enabled: related,
    });
  }
  return <form className="shortlist-refinement" onSubmit={submit} aria-label="Shortlist filters">
    <div className="shortlist-filter-grid">
      <label>Background<input required minLength={2} maxLength={Math.max(180,originalBackground.length)} value={background} onChange={event=>setBackground(event.target.value)}/></label>
      <label>Roles<input required maxLength={365} value={roles} onChange={event=>{setRoles(event.target.value);setConcepts({});}}/></label>
      <label>Skills<input maxLength={2100} value={skills} onChange={event=>setSkills(event.target.value)}/></label>
      <label>Location<input placeholder="Anywhere in the UK" maxLength={100} value={location} onChange={event=>{
        const value=event.target.value;
        setLocation(value);
        if(value.trim()&&mode==='anywhere')setMode('prefer_area');
        if(!value.trim())setMode('anywhere');
      }}/></label>
      <label>Industries<input maxLength={250} value={industries} onChange={event=>setIndustries(event.target.value)}/></label>
    </div>
    {choices.map(({index,options})=><label key={index}>Profession for {split(roles)[index]}
      <select required value={concepts[index]||''} onChange={event=>setConcepts(current=>({...current,[index]:event.target.value}))}>
        <option value="">Choose a profession</option>
        {options.map(option=><option key={option.concept_id} value={option.concept_id}>{option.label}</option>)}
      </select>
    </label>)}
    <div className="shortlist-filter-actions">
      <details><summary>Search options</summary>
        <label>Location preference<select value={mode} onChange={event=>setMode(event.target.value as LocationMode)}>
          <option value="anywhere">Anywhere in the UK</option><option value="prefer_area">Prefer selected areas</option><option value="selected_area">Only selected areas</option>
        </select></label>
        <label className="checkbox-line"><input type="checkbox" checked={related} onChange={event=>setRelated(event.target.checked)}/>Include related roles</label>
      </details>
      {creditMode&&<small>Up to 1 credit</small>}
      <button type="submit" className="button small">Refine search</button>
    </div>
    {(validation||error)&&<p className="error" role="alert">{validation||error}</p>}
  </form>;
}
