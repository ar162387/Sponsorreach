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
  location: { preferred_regions: string[]; relocate: boolean; strict: boolean };
  related_roles_enabled: boolean;
};
export type EmployerCard = {
  bookmarked?: boolean; session_id?: string | null;
  employer_id: string; name: string; town: string; group: 'direct' | 'related';
  explanation: { text: string; summary?: string; basis: string; sources: { url: string; excerpt: string; observed_at: string }[]; skill_hits: string[] };
  tags: string[];
  channels: { kind: string; value: string; source_url: string; observed_at: string | null; label?: string; display_value?: string; linkable?: boolean; note?: string }[];
  sponsor: { status: string; snapshot_date: string };
  verified_open_vacancies: { title: string; url: string }[];
  is_demo: boolean; workplace_location_known: boolean;
};
export type LoadingContext = { roles: string[]; background: string; specialization: string; skills: string[]; locations: string[]; related_roles_enabled: boolean };
export type VisaContext = { route: string; expiry: string | null };
export type MatchSession = {
  credit_mode?:boolean; next_locked_batch?:number|null; balance?:number; next_batch_cost?:number|null; search_credit_charged?:boolean; repeat_credit_saved?:boolean;
  profile?: Profile; visa_context?: VisaContext | null;
  starred?: boolean; revision?: number; next_cursor?: number | null;
  loading_context?: LoadingContext;
  verification_required?: boolean;
  session_id: string; status: string; stage: string; access: string; error_code?: string;
  preview?: EmployerCard[]; total_count?: number; locked_count?: number;
  direct_count?: number; related_count?: number; is_demo?: boolean; demo_price_gbp: number;
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
    throw Object.assign(new Error(message), { status: response.status, code: detail?.code, field });
  }
  return data;
}
