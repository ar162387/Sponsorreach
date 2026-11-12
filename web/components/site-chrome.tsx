'use client';

import { usePathname } from 'next/navigation';
import s from '@/app/landing.module.css';

function useWorkspace(signedIn: boolean) {
  const path = usePathname();
  return signedIn && /^\/(account|admin)(\/|$)/.test(path);
}

export default function SiteChrome({children, signedIn}: {children: React.ReactNode; signedIn: boolean}) {
  return useWorkspace(signedIn) ? null : <>{children}</>;
}

export function SiteMain({children, signedIn}: {children: React.ReactNode; signedIn: boolean}) {
  const isPublic = !useWorkspace(signedIn);
  return (
    <main id="main" tabIndex={-1} className={isPublic ? s.publicMain : undefined} data-atlas-landing={isPublic || undefined}>
      {children}
    </main>
  );
}
