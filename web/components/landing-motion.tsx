'use client';

import { useEffect, useRef, useState } from 'react';


/** Decorative enhancement only: every word and control works without this component. */
export default function LandingMotion() {
  const paused = false;
  const [reduced, setReduced] = useState(false);
  const seen = useRef(new WeakSet<Element>());

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion reduce)');
    const update = () => setReduced(preference.matches);
    update();
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    const root = document.querySelector<HTMLElement>('[data-atlas-landing]');
    if (!root) return;
    const disabled = paused || reduced || window.matchMedia('(prefers-reduced-motion reduce)').matches;
    root.dataset.motion = disabled ? 'off' : 'on';
    if (disabled) {
      root.getAnimations({ subtree: true }).forEach(animation => animation.cancel());
      return;
    }
    const animations = new Set<Animation>();
    const play = (element: HTMLElement, frames: Keyframe[], options: KeyframeAnimationOptions) => {
      const animation = element.animate(frames, options);
      animations.add(animation);
      animation.onfinish = () => animations.delete(animation);
    };
    const reveal = (element: HTMLElement) => {
      if (seen.current.has(element)) return;
      seen.current.add(element);
      // Enhance readable content only: no hidden pre-scroll state or scroll interception.
      const kind = element.dataset.atlasReveal;
      let from = 'translateY(24px)';
      let to = 'translateY(0)';
      if (kind === 'row') { from = 'translateX(-18px)'; to = 'translateX(0)'; }
      if (kind === 'turn') { from = 'rotate(-35deg) scale(.8)'; to = 'rotate(12deg) scale(1)'; }
      if (kind === 'connector') {
        const mobile = window.matchMedia('(max-width:600px)').matches;
        from = mobile ? 'scaleY(.15)' : 'scaleX(.15)';
        to = mobile ? 'scaleY(1)' : 'scaleX(1)';
      }
      play(element, [{ opacity: .25, transform: from }, { opacity: 1, transform: to }], {
        duration: 700, delay: Math.min(Number(element.dataset.atlasDelay) || 0, 160), easing: 'cubic-bezier(.16,1,.3,1)',
      });
      element.querySelectorAll<HTMLElement>('[data-atlas-accent]').forEach(accent => {
        play(accent, [{ transform: 'scale(.7) rotate(-12deg)' }, { transform: 'scale(1.08) rotate(3deg)', offset: .65 }, { transform: 'scale(1) rotate(0)' }], { duration: 850, delay: 120, easing: 'ease-out' });
      });
    };
    const opening = root.querySelector<HTMLElement>('section');
    const visibility = () => { root.dataset.tabVisible = document.hidden ? 'false' : 'true'; };
    visibility();
    document.addEventListener('visibilitychange', visibility);
    const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.target === opening) {
          opening.dataset.inView = entry.isIntersecting ? 'true' : 'false';
        } else if (entry.isIntersecting) {
          reveal(entry.target as HTMLElement);
          observer?.unobserve(entry.target);
        }
      });
    }, { threshold: .18 }) : null;
    if (opening) observer?.observe(opening);
    root.querySelectorAll<HTMLElement>('[data-atlas-reveal]').forEach(element => observer?.observe(element));
    const onToggle = (event: Event) => {
      const details = event.target;
      if (!(details instanceof HTMLDetailsElement) || !details.open) return;
      const answer = details.querySelector('p');
      if (!answer) return;
      const animation = answer.animate([{ opacity: .4, transform: 'translateY(-4px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 220, easing: 'ease-out' });
      animations.add(animation);
      animation.onfinish = () => animations.delete(animation);
    };
    root.addEventListener('toggle', onToggle, true);
    return () => {
      observer?.disconnect();
      document.removeEventListener('visibilitychange', visibility);
      root.removeEventListener('toggle', onToggle, true);
      animations.forEach(animation => animation.cancel());
    };
  }, [paused, reduced]);

  return null;
}
