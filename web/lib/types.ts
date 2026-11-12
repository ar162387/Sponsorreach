export type LocationMode = 'anywhere' | 'prefer_area' | 'selected_area';
export type ProfessionChoice = { index: number; options: { concept_id: string; label: string }[] };
type EvidenceRef = { claim_id: string; text: string; source_url: string };
type MatchEvidence = {
  version: string;
  profession: { label: string; concept_id: string | null; sources: EvidenceRef[] };
  location: { status: 'match' | 'out_of_area' | 'unknown' | 'unrestricted'; sources: { type: 'company_address' | 'recorded_workplace'; field: string; value: string; matches_area?: boolean }[] };
  skills: { recorded: (EvidenceRef & { label: string })[]; not_recorded: string[] };
  industry: (EvidenceRef & { label: string })[];
  early_career: EvidenceRef | null;
  hiring_basis: string;
  matching_vacancies: { title: string; url: string }[];
};
export type Profile = {
  profile_version: 1;
  background: { subject: string; specialization: string };
  role_intents: { raw_label: string; concept_id?: string | null; confirmed: boolean }[];
  explore: boolean;
  career_stage: 'student' | 'graduate' | 'experienced' | 'career_changer';
  skills: { label: string; source: 'user' }[];
  experience_summary: string;
  preferred_industries: string[];
  certifications: string[];
  location: { preferred_regions: string[]; relocate: boolean; strict: boolean; mode?: LocationMode | null };
  related_roles_enabled: boolean;
};
export type EmployerCard = {
  bookmarked?: boolean; session_id?: string | null; added_revision?: number;
  employer_id: string; name: string; town: string; group: 'direct' | 'related'; location_section?: 'main' | 'unknown';
  explanation: { text: string; summary?: string; basis: string; sources: { url: string; excerpt: string; observed_at: string }[]; skill_hits: string[]; evidence?: MatchEvidence };
  tags: string[];
  channels: { kind: string; value: string; source_url: string; observed_at: string | null; label?: string; display_value?: string; linkable?: boolean; note?: string }[];
  sponsor: { status: string; snapshot_date: string };
  verified_open_vacancies: { title: string; url: string }[];
  is_demo: boolean; workplace_location_known: boolean;
};
export type LoadingContext = { roles: string[]; background: string; specialization: string; skills: string[]; locations: string[]; related_roles_enabled: boolean };
export function matchingContext(profile: Profile): LoadingContext {
  return {
    roles: profile.role_intents.map(role => role.raw_label),
    background: profile.background.subject,
    specialization: profile.background.specialization,
    skills: profile.skills.slice(0, 5).map(skill => skill.label),
    locations: profile.location.preferred_regions,
    related_roles_enabled: profile.related_roles_enabled,
  };
}
export type VisaContext = { route: string; expiry: string | null };
export type MatchSession = {
  credit_mode?:boolean; next_locked_batch?:number|null; balance?:number; next_batch_cost?:number|null; search_credit_charged?:boolean; repeat_credit_saved?:boolean; refinement_empty?:boolean;
  profile?: Profile; visa_context?: VisaContext | null;
  starred?: boolean; revision?: number; next_cursor?: number | null;
  loading_context?: LoadingContext;
  verification_required?: boolean;
  session_id: string; status: string; stage: string; access: string; error_code?: string;
  preview?: EmployerCard[]; total_count?: number; locked_count?: number;
  unknown_location_count?: number; empty_reason?: 'location' | 'eligibility' | 'profession';
  direct_count?: number; related_count?: number; is_demo?: boolean;
};
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch('/api/' + path, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers }, cache: 'no-store' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const validation = Array.isArray(detail) ? detail[0] : undefined;
    const field = validation?.loc?.filter((value: unknown) => value !== 'body').join('.');
    const clarification = detail?.normalization?.clarification;
    const label = field?.includes('role_intents') ? 'desired role' : field?.includes('background') ? 'background' : field?.includes('skills') ? 'skills' : field?.includes('location') ? 'location preferences' : 'details';
    const fallback = response.status >= 500 ? 'Your search service is temporarily unavailable. Your details are saved; please try again shortly.' : 'We couldn’t complete this step. Please try again.';
    const message = typeof detail === 'string' ? detail : clarification || (validation ? validation.type === 'extra_forbidden' ? 'This page is out of date. Reload it and try your saved search again.' : `Please check your ${label}: ${validation.msg}` : data.error || fallback);
    throw Object.assign(new Error(message), { status: response.status, code: detail?.code, choices: detail?.normalization?.choices, field });
  }
  return data;
}
