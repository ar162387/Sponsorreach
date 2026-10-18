'use client';
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <html lang="en-GB"><body style={{ fontFamily: 'sans-serif', maxWidth: 600, margin: '80px auto', padding: 24, color: '#0B3B5B' }}><h1>Let’s reconnect SponsorReach.</h1><p>We couldn’t load your workspace or check your sign-in. Please retry in a moment.</p><button onClick={reset} style={{ padding: '12px 24px', cursor: 'pointer' }}>Try again</button></body></html>;
}
