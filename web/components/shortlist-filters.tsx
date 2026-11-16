'use client';

import { useState } from 'react';
import type { Profile, ProfessionChoice } from '@/lib/types';
import SearchProfileForm from './search-profile-form';

export default function ShortlistFilters({ profile, creditMode, onRefine, choices, error }: {
  profile: Profile;
  creditMode?: boolean;
  choices: ProfessionChoice[];
  error: string;
  onRefine: (profile: Profile) => void;
}) {
  const [draft, setDraft] = useState(profile);
  const [clearedChoices, setClearedChoices] = useState(false);
  const [edited, setEdited] = useState(false);
  return <section className="shortlist-refinement" aria-label="Refine shortlist">
    <header><h3>Search criteria</h3></header>
    <SearchProfileForm profile={draft} choices={clearedChoices ? [] : choices} name="Shortlist filters"
      onChange={(value, resetChoices) => {
        setDraft(value);
        setEdited(true);
        if (resetChoices) setClearedChoices(true);
      }}
      onSubmit={onRefine} submitLabel="Refine search" error={edited ? '' : error}
      detail={creditMode ? <small>Up to 1 credit. Empty or mostly repeated results are free.</small> : undefined}/>
  </section>;
}
