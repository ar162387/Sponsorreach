const workspacePaths = new Set([
  '/account', '/account/search', '/account/shortlists?new=1', '/account/billing', '/account/shortlists',
  '/account/saved', '/account/settings', '/account/support',
]);

export function signinDestination(value: unknown): string {
  if (typeof value === 'string' && (workspacePaths.has(value) ||
    /^\/account\/shortlists\?shortlist=[a-f0-9-]{36}(&edit=1)?$/.test(value))) return value;
  return '/account';
}

export function signinUrl(status = 'open', destination = '/account') {
  const params = new URLSearchParams({ signin: status });
  if (destination !== '/account') params.set('returnTo', destination);
  return '/?' + params;
}
