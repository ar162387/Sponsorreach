'use client';

import { useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { ArrowRight, Plus, X } from 'lucide-react';
import type { Profile, ProfessionChoice } from '@/lib/types';

const kinds = {
  role: { label: 'Role', example: 'e.g. Software engineer', max: 3, length: 120 },
  skill: { label: 'Skill', example: 'e.g. Python', max: 20, length: 100 },
  location: { label: 'Location', example: 'e.g. Manchester', max: 5, length: 100 },
  industry: { label: 'Industry', example: 'e.g. Healthcare', max: 5, length: 100 },
} as const;

type Kind = keyof typeof kinds;
type Entry = { kind: Kind; text: string };

const broadRoles = new Set(['analyst', 'engineer', 'consultant', 'manager', 'business', 'graduate']);
const sameLabel = (left: string, right: string) => left.toLowerCase() === right.toLowerCase();

function tags(profile: Profile, kind: Kind) {
  switch (kind) {
    case 'role': return profile.role_intents.map(role => role.raw_label).filter(Boolean);
    case 'skill': return profile.skills.map(skill => skill.label);
    case 'location': return profile.location.preferred_regions;
    case 'industry': return profile.preferred_industries;
  }
}

function withoutRoleConcepts(profile: Profile): Profile['role_intents'] {
  return profile.role_intents.map(role => ({ ...role, concept_id: null }));
}

function withLocations(profile: Profile, regions: string[]): Profile {
  const existing = profile.location;
  const strict = existing.mode === 'selected_area' || (!existing.mode && existing.strict && !existing.relocate);
  const mode = regions.length ? (strict ? 'selected_area' : 'prefer_area') : 'anywhere';
  return { ...profile, location: { preferred_regions: regions, mode, relocate: false, strict: mode === 'selected_area' } };
}

function addEntry(profile: Profile, entry: Entry): Profile {
  const { kind, text } = entry;
  const label = text.trim();
  if (!label) return profile;
  if (kind === 'role' && label.length < 2) throw new Error('Use at least two characters for a role.');
  const existing = tags(profile, kind);
  if (existing.some(tag => sameLabel(tag, label))) return profile;
  const { max, length } = kinds[kind];
  if (label.length > length) throw new Error(`Keep each ${kinds[kind].label.toLowerCase()} within ${length} characters.`);
  if (existing.length >= max) throw new Error(`You can add up to ${max} ${kinds[kind].label.toLowerCase()}s.`);
  switch (kind) {
    case 'role': return { ...profile, role_intents: [...profile.role_intents.filter(role => role.raw_label), { raw_label: label, confirmed: false }] };
    case 'skill': return { ...profile, skills: [...profile.skills, { label, source: 'user' }], role_intents: withoutRoleConcepts(profile) };
    case 'location': return withLocations(profile, [...existing, label]);
    case 'industry': return { ...profile, preferred_industries: [...existing, label] };
  }
}

function removeEntry(profile: Profile, kind: Kind, index: number): Profile {
  switch (kind) {
    case 'role': return { ...profile, role_intents: profile.role_intents.filter((_, i) => i !== index) };
    case 'skill': return { ...profile, skills: profile.skills.filter((_, i) => i !== index), role_intents: withoutRoleConcepts(profile) };
    case 'location': return withLocations(profile, profile.location.preferred_regions.filter((_, i) => i !== index));
    case 'industry': return { ...profile, preferred_industries: profile.preferred_industries.filter((_, i) => i !== index) };
  }
}

function TagField({ label, types, entry, profile, hint, onChange, onAdd, onRemove, inputRef }: {
  label: string;
  types: [Kind, Kind];
  entry: Entry;
  profile: Profile;
  hint: string;
  onChange: (entry: Entry) => void;
  onAdd: () => void;
  onRemove: (kind: Kind, index: number) => void;
  inputRef?: React.RefObject<HTMLInputElement | null>;
}) {
  const id = useId();
  const fieldRef = useRef<HTMLInputElement>(null);
  const input = inputRef ?? fieldRef;
  return <div className="search-tag-field">
    <label htmlFor={id}>{label}</label>
    <div className="search-tag-input">
      <select aria-label={label + ' type'} value={entry.kind} onChange={event => onChange({ ...entry, kind: event.target.value as Kind })}>
        {types.map(kind => <option key={kind} value={kind}>{kinds[kind].label}</option>)}
      </select>
      <input ref={input} id={id} value={entry.text} maxLength={kinds[entry.kind].length} enterKeyHint="done"
        placeholder={kinds[entry.kind].example} aria-describedby={id + '-hint'}
        onInput={event => onChange({ ...entry, text: event.currentTarget.value })}
        onKeyDown={event => {
          if (event.key !== 'Enter' || event.nativeEvent.isComposing) return;
          event.preventDefault();
          if (entry.text.trim()) onAdd();
        }}/>
      <button type="button" className="search-tag-add" aria-label={'Add ' + kinds[entry.kind].label.toLowerCase()} disabled={!entry.text.trim()}
        onClick={() => { onAdd(); input.current?.focus(); }}><Plus size={18}/></button>
    </div>
    <small id={id + '-hint'}>{hint}</small>
    {types.some(kind => tags(profile, kind).length > 0) && <ul className="search-tags" aria-label={'Added ' + label.toLowerCase()}>
      {types.flatMap(kind => tags(profile, kind).map((value, index) => <li key={kind + '-' + index}>
        <button type="button" data-kind={kind} aria-label={`Remove ${kinds[kind].label.toLowerCase()} ${value}`}
          onClick={() => { onRemove(kind, index); input.current?.focus(); }}>
          <span className="search-tag-kind">{kinds[kind].label}</span> <span>{value}</span><X size={13} aria-hidden="true"/>
        </button>
      </li>))}
    </ul>}
  </div>;
}

export default function SearchProfileForm({ profile, choices, onChange, onSubmit, submitLabel, disabled, error, detail, name }: {
  profile: Profile;
  choices: ProfessionChoice[];
  onChange: (profile: Profile, resetChoices: boolean) => void;
  onSubmit: (profile: Profile) => void;
  submitLabel: string;
  disabled?: boolean;
  error?: string;
  detail?: ReactNode;
  name: string;
}) {
  const id = useId();
  const roleInput = useRef<HTMLInputElement>(null);
  const [work, setWork] = useState<Entry>({ kind: 'role', text: '' });
  const [preference, setPreference] = useState<Entry>({ kind: 'location', text: '' });
  const [validation, setValidation] = useState('');
  const background = [profile.background.subject, profile.background.specialization].filter(Boolean).join(' · ');
  const { location } = profile;
  const locationMode = location.mode ?? (location.relocate ? 'anywhere' : location.strict ? 'selected_area' : 'prefer_area');
  const locationHint = !location.preferred_regions.length
    ? 'Optional. Leave locations blank to search anywhere in the UK.'
    : locationMode === 'anywhere' ? 'The current search covers the whole UK.'
    : locationMode === 'selected_area' ? 'Only search your selected locations.' : 'Searches favour your selected locations.';

  function change(next: Profile, resetChoices: boolean) {
    setValidation('');
    onChange(next, resetChoices);
  }

  function commit(entry: Entry, clear: (entry: Entry) => void) {
    try {
      const next = addEntry(profile, entry);
      if (next !== profile) change(next, entry.kind === 'role' || entry.kind === 'skill');
      clear({ ...entry, text: '' });
    } catch (problem) {
      setValidation((problem as Error).message);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (disabled) return;
    try {
      const next = addEntry(addEntry(profile, work), preference);
      const roles = next.role_intents.filter(role => role.raw_label.trim());
      if (next.background.subject.trim().length < 2) throw new Error('Enter your degree, field of study or professional background.');
      if (!roles.length) throw new Error('Add at least one target role.');
      const broad = roles.find(role => !role.concept_id && broadRoles.has(role.raw_label.trim().toLowerCase()));
      if (broad) {
        roleInput.current?.focus();
        throw new Error(`Which type of ${broad.raw_label.toLowerCase()} role interests you? Add a specific title, then remove the broad role.`);
      }
      setValidation('');
      setWork({ ...work, text: '' });
      setPreference({ ...preference, text: '' });
      onSubmit({ ...next, background: { ...next.background, subject: next.background.subject.trim() }, role_intents: roles });
    } catch (problem) {
      setValidation((problem as Error).message);
    }
  }

  return <form className="workspace-search-form" aria-label={name} onSubmit={submit}>
    <div className="search-background-field">
      <label htmlFor={id}>Degree or professional background</label>
      <input id={id} required minLength={2} maxLength={Math.max(180, background.length)} value={background}
        placeholder="e.g. Mechanical Engineering, Accounting, Nursing"
        onInput={event => change({ ...profile, background: { subject: event.currentTarget.value, specialization: '' }, role_intents: withoutRoleConcepts(profile) }, true)}/>
    </div>
    <div className="search-fields">
      <TagField label="Roles and skills" types={['role', 'skill']} entry={work} profile={profile} onChange={setWork}
        hint="Add at least one role. Press Enter after each role or skill."
        onAdd={() => commit(work, setWork)} onRemove={(kind, index) => change(removeEntry(profile, kind, index), true)} inputRef={roleInput}/>
      <TagField label="Locations and industries" types={['location', 'industry']} entry={preference} profile={profile} onChange={setPreference}
        hint={locationHint}
        onAdd={() => commit(preference, setPreference)} onRemove={(kind, index) => change(removeEntry(profile, kind, index), false)}/>
    </div>
    {choices.map(({ index, options }) => <label className="search-clarification" key={index}>Profession for {profile.role_intents[index]?.raw_label}
      <select required value={profile.role_intents[index]?.concept_id || ''} onChange={event => {
        const concept_id = event.target.value || null;
        change({ ...profile, role_intents: profile.role_intents.map((role, i) => i === index ? { ...role, concept_id, confirmed: !!concept_id } : role) }, false);
      }}>
        <option value="">Choose a profession</option>
        {options.map(option => <option key={option.concept_id} value={option.concept_id}>{option.label}</option>)}
      </select>
    </label>)}
    {(validation || error) && <p className="search-form-error" role="alert">{validation || error}</p>}
    <div className="search-form-actions">{detail}<button className="button small" type="submit"
      disabled={disabled || choices.some(choice => !profile.role_intents[choice.index]?.concept_id)}>{submitLabel}<ArrowRight size={16}/></button></div>
  </form>;
}
