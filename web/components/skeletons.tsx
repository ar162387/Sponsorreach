export function CompanySkeletons({ count = 3 }: { count?: number }) {
  return <div className="company-skeletons" role="status" aria-label="Loading saved companies"><span className="sr-only">Loading saved companies…</span>{Array.from({ length: count }, (_, index) => <div className="company-skeleton" key={index} aria-hidden="true"><div className="skeleton-line short"/><div className="skeleton-line title"/><div className="skeleton-line"/><div className="skeleton-line medium"/><div className="skeleton-actions"><i/><i/><i/></div></div>)}</div>;
}
export function ResultsSkeleton({ embedded = false }: { embedded?: boolean }) {
  return <section className={embedded ? 'saved-results-loading' : 'shell results-skeleton'} aria-label="Opening saved shortlist"><div className="skeleton-line title" aria-hidden="true"/><div className="skeleton-line medium" aria-hidden="true"/><CompanySkeletons/></section>;
}
export function WorkspaceSkeleton() {
  return <section className="research-workspace workspace-skeleton" role="status" aria-label="Opening workspace"><div className="skeleton-line title" aria-hidden="true"/><div className="workspace-columns"><aside aria-hidden="true">{Array.from({ length: 5 }, (_, index) => <div className="company-skeleton" key={index}><div className="skeleton-line"/><div className="skeleton-line short"/></div>)}</aside><CompanySkeletons/></div></section>;
}
