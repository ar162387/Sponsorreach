import type { LoadingContext } from './types';

export function loadingMessages(context?: LoadingContext): string[] {
  const clean = (value: string) => value.replace(/\s+/g, ' ').trim().slice(0, 140);
  const messages = ['Your shortlist is built around your professional interests.'];
  if (context?.roles.length) messages.push(`Your target ${context.roles.length === 1 ? 'role' : 'roles'}: ${context.roles.map(clean).join(' · ')}.`);
  if (context?.specialization) messages.push(`Your niche matters: ${clean(context.specialization)}.`);
  if (context?.skills.length) messages.push(`Your selected skills: ${context.skills.slice(0, 3).map(clean).join(', ')}.`);
  if (context?.background) messages.push(`Your ${clean(context.background)} background adds context to your search.`);
  messages.push('Employer activities and professional functions help explain each match.');
  if (context?.locations.length) messages.push(`Your location preference: ${context.locations.map(clean).join(' · ')}.`);
  messages.push('Available contact routes help you decide who to approach.');
  if (context?.related_roles_enabled) messages.push('You chose to explore related careers in a separate section.');
  messages.push('Your recommendations will be saved so you can return to them.');
  return messages;
}

// Allow at least six seconds, and more time for longer personalised captions.
export function captionDuration(message: string): number {
  return Math.max(6000, Math.min(15000, message.trim().split(/\s+/).length * 300));
}
