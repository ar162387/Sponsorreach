'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import CreditAllowance from './credit-allowance';
import { refreshCredits } from './dashboard-shell';
import SearchProfileForm from './search-profile-form';
import { searchRequest } from '@/lib/search-request';
import { api, type Profile, type ProfessionChoice } from '@/lib/types';

const initialProfile: Profile = {
  profile_version: 1,
  background: { subject: '', specialization: '' },
  role_intents: [],
  explore: false,
  career_stage: 'graduate',
  skills: [],
  experience_summary: '',
  preferred_industries: [],
  certifications: [],
  location: { preferred_regions: [], relocate: false, strict: false },
  related_roles_enabled: false,
};

export default function Intake({ onCancel, onComplete }: {
  onCancel: () => void;
  onComplete: (id: string, profile: Profile) => void;
}) {
  const [profile, setProfile] = useState(initialProfile);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [creditBalance, setCreditBalance] = useState<number | null>(null);
  const [choices, setChoices] = useState<ProfessionChoice[]>([]);
  const submission = useRef<{ profile: string; key: string } | null>(null);
  const inFlight = useRef(false);
  const dialog = useRef<HTMLDialogElement>(null);

  useLayoutEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => { element?.close(); };
  }, []);

  async function submit(current: Profile) {
    if (inFlight.current || creditBalance === 0) return;
    inFlight.current = true;
    setProfile(current);
    setError('');
    setBusy(true);
    try {
      const payload = JSON.stringify(current);
      if (submission.current?.profile !== payload) submission.current = { profile: payload, key: crypto.randomUUID() };
      const result = await api<{ session_id: string }>('matches', {
        method: 'POST',
        body: JSON.stringify(searchRequest({ profile: current, visaContext: null, creditConsent: true, idempotencyKey: submission.current.key })),
      });
      refreshCredits();
      onComplete(result.session_id, current);
    } catch (problem) {
      const failure = problem as Error & { status?: number; choices?: ProfessionChoice[] };
      if (failure.status === 402) {
        setCreditBalance(0);
        refreshCredits();
      }
      if (failure.choices?.length) setChoices(failure.choices);
      setError(failure.message);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return <dialog className="new-shortlist-dialog" ref={dialog} aria-labelledby="new-shortlist-title"
    onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <div className="new-shortlist-content">
      <header>
        <div><h2 id="new-shortlist-title">New search</h2><p>Find UK sponsors that fit the work you want to do.</p></div>
        <button type="button" className="icon-button" aria-label="Close new search" onClick={onCancel} disabled={busy}><X size={21}/></button>
      </header>
      <CreditAllowance onBalance={setCreditBalance}/>
      <SearchProfileForm profile={profile} choices={choices} name="New shortlist search"
        onChange={(value, resetChoices) => { setProfile(value); setError(''); if (resetChoices) setChoices([]); }}
        onSubmit={submit} error={error} disabled={busy || creditBalance === 0}
        submitLabel={busy ? 'Starting search…' : 'Find sponsors'}
        detail={<small>Up to 1 credit. Empty or mostly repeated results are free.</small>}/>
    </div>
  </dialog>;
}
