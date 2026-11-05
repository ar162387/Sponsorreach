# Landing-page design — Research Atlas

30 October 2026. Implemented locally; not deployed.

## Research and rationale

Reviewed Welcome to the Jungle UK (formerly Otta), Sponsor Finder and Are.na. Welcome to the Jungle's distinctive colour/typography helps establish a recognisable identity; Sponsor Finder presents a narrative around sponsor research; Are.na is an adjacent reference for organising and explaining information. These are visual/product references, not endorsements or independently verified conversion evidence.

- https://uk.welcometothejungle.com/
- https://www.sponsorfinder.io/
- https://www.are.na/
- https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- https://www.nngroup.com/articles/progressive-disclosure/

The rationale uses hierarchy (size, contrast and grouping) to establish a reading order, and expandable answers to defer secondary detail. No claim is made that a particular colour produces a psychological response or measured conversion gain. Usability and conversion performance need evaluation with actual prospective users.

## Direction implemented

Muted olive opening, warm sand research diagram, khaki field notes, forest FAQ and rust accents. Serif display type contrasts with the existing readable sans-serif body. A centred opening replaces the split hero. The research journey uses connected nodes, not company cards; the information section uses numbered editorial rows. Section typography, rules and spacing create rhythm without repeated rounded boxes. A custom landing masthead and oversized closing wordmark finish the composition.

The diagram describes the service rather than fabricating company results. Existing availability statements, source limitations and free-access information remain truthful. There are no invented trust badges, testimonials, counts or promises of employment.

## Isolation and verification

Changes are limited to app/page.tsx and app/landing.module.css. Home-only body/header/footer selectors are conditional on the landing marker. CSS module rules do not override the application on other routes.

SHA1 checks before/after confirmed unchanged:
- intake.tsx: 8ae6001c3779e50c2d58457d1a290c57aa7f1bda
- results.tsx: de220515d084188fe744b308a1b8468a0e4d5bf9
- account.tsx: 963925e36607718c4dc309216eac296d28ab96b4
- layout.tsx: 1a580fa95dd20f32614ae1c7a2ad768354c52c73

Production build and TypeScript passed. Browser checks at 320, 390, 768 and 1440px confirmed no horizontal overflow and one visible header. FAQ expansion passed. Client navigation from the landing CTA to /match restored the existing header and original rgb(250, 251, 248) background; the landing marker disappeared. Intake/results/account functionality is unchanged and not revalidated end to end in this frontend-only preview. Mobile and desktop screenshots were visually inspected. Reduced-motion preferences disable button movement.

Local design preview: http://127.0.0.1:3020/

## Restrained motion and original logo — 30 October

Research references: https://www.nngroup.com/articles/animation-usability/ and https://web.dev/articles/prefers-reduced-motion . Linear and Stripe were also reviewed as adjacent product-site references; no source code, animation engine or proprietary assets were imported. This is an original, dependency-free implementation.

- Native Web Animations/IntersectionObserver animate 14 marked elements once per mounted landing page: 520ms, 12px, at most 180ms stagger. Content starts readable and works with JavaScript disabled. No scroll handler, scroll-linked transform, parallax, pinned content or reading gate.
- Ambient circles drift 6px horizontally/12px vertically for two finite cycles, then settle. A visible pause control cancels active animations and disables CSS transitions; OS reduced-motion preferences override decorative motion and disable the toggle. Preference changes are observed live.
- Buttons/arrows, research nodes and editorial rows provide brief hover feedback; native details receive a 220ms opening transition and rotating plus indicator. Native keyboard and link behaviour remain.
- Navbar uses the original SR mark instead of the compass. Original raster artwork remains unchanged. The browser favicon is an SVG composition of the original miniature on a pale rounded backing; its embedded data is self-contained. The old transparent app/icon.png was preserved as public/brand/tab-mark-original.png and removed from automatic favicon selection. Explicit metadata selects /icon.svg?v=3 to avoid competing/stale entries. Apple touch icon is unchanged.
- Build/TypeScript passed. Browser checks confirmed pause -> zero animations; reduced motion -> zero animations and all marked content opacity 1; FAQ works; 320/390/768/1440px have no horizontal overflow; navbar image loads and favicon returns 200 with correct backing and one icon entry. Original intake/results/account source hashes remain unchanged. Navigation to /match removes motion controls and restores the original background/header. Backend account/catalogue requests are unavailable in this frontend-only preview; matching/sign-in were not tested end to end.
- Final local preview: http://127.0.0.1:3024/ . Not deployed.


## Internal theme extension — 30 October, subsequent request

The later request explicitly extends this visual direction to all internal pages and components, superseding the earlier home-only scope. See [INTERNAL_THEME_VERIFICATION.md](INTERNAL_THEME_VERIFICATION.md) for current scope and checks. The earlier hashes and ports record the prior landing-only stages, not the current implementation.


## Touch-first motion revision — 31 October

Replaces the previous finite three-circle drift with eight continuously drifting circles. Independent durations and negative offsets avoid synchronised movement. Decoration stays behind content and does not receive input. IntersectionObserver pauses the circles outside the hero; hidden tabs pause them too. Pause and OS reduced motion stop all landing animation.

Viewport entry now animates research steps (24px rise), connecting arrows (direction-aware scaling), editorial/FAQ rows (18px slide), step/row accents (brief scale/rotation) and the closing asterisk. Entrances play once per mount. No scroll listener, scroll hijacking, pinned section or hidden pre-scroll content. Reading and links work without animation.

Final production build and TypeScript passed. At 390px, browser checks confirmed eight infinite animations, changing bubble transforms over time, step/row entrance on scroll, all bubbles paused when the hero leaves view, Pause -> zero animations, reduced motion -> zero animations, and working FAQ expansion. No overflow at 320/390/768/1440px. Mobile screenshot visually inspected. Navigation to /match removes landing motion and retains the internal sand theme. No backend changes or deployment.

Latest local preview: http://127.0.0.1:3032/ . Earlier preview URLs document prior iterations.
