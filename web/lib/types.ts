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
  employer_id: string; name: string; town: string; group: 'direct' | 'related';
  explanation: { text: string; summary?: string; basis: string; sources: { url: string; excerpt: string; observed_at: string }[]; skill_hits: string[] };
  tags: string[];
  channels: { kind: string; value: string; source_url: string; observed_at: string | null; label?: string; display_value?: string; linkable?: boolean; note?: string }[];
  sponsor: { status: string; snapshot_date: string };
  verified_open_vacancies: { title: string; url: string }[];
  is_demo: boolean; workplace_location_known: boolean;
};
export type MatchSession = {
  verification_required?: boolean;
  session_id: string; status: string; stage: string; access: string; error_code?: string;
  preview?: EmployerCard[]; total_count?: number; locked_count?: number;
  direct_count?: number; related_count?: number; is_demo?: boolean; demo_price_gbp: number;
};
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch('/api/' + path, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers }, cache: 'no-store' });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.error || 'We couldn’t complete this step. Please try again.');
  return data;
}
