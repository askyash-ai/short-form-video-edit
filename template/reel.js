/* reel.js: timeline helpers for the reel template. Load after gsap, call reelKit(tl) once, then use the helpers.
   Everything is a tween on the one paused timeline, so any frame seeks (renders, snapshots) the same way. */
function reelKit(tl) {
  const $ = s => document.querySelector(s);
  // CLOSED is invisible (zero area), so a panel that shares a clip window with others never peeks out before its word,
  // even on a backward seek (GSAP renders a not-yet-started fromTo at its from state)
  const CLOSED = 'inset(50% 50% 50% 50% round 999px)', PILL = 'inset(38% 34% 38% 34% round 999px)', OPEN = r => `inset(0% 0% 0% 0% round ${r}px)`;
  const radius = el => parseFloat(getComputedStyle(el).borderTopLeftRadius) || 34;

  // liquid glass in: the panel grows out of a pill (clip-path, so backdrop-filter stays live), lifts 26 px,
  // a sheen sweeps across, then the content arrives in order ([data-c] children, else direct children)
  function lgIn(sel, t, o = {}) {
    const el = $(sel); if (!el) return;
    const r = radius(el) > 400 ? 999 : radius(el);
    // closed -> a droplet pill (0.12 s) -> the full panel (expo.out): the "liquid" grow
    tl.fromTo(el, { clipPath: CLOSED, y: o.y ?? 26 }, { clipPath: o.from || PILL, duration: 0.12, ease: 'power2.out' }, t);
    tl.to(el, { clipPath: OPEN(r), y: 0, duration: o.d || 0.5, ease: 'expo.out' }, t + 0.12);
    tl.fromTo(el, { '--sheen': '-160%' }, { '--sheen': '320%', duration: 0.9, ease: 'power2.inOut' }, t + 0.12);
    const kids = el.querySelectorAll(':scope [data-c]').length ? el.querySelectorAll(':scope [data-c]') : el.children;
    tl.fromTo(kids, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.32, ease: 'power2.out', stagger: o.stagger ?? 0.08 }, t + 0.14);
  }
  // liquid glass out: back into a pill, ending just before the clip window closes
  function lgOut(sel, tEnd, d = 0.26) {
    const el = $(sel); if (!el) return;
    tl.to(el, { clipPath: PILL, y: -10, duration: d * 0.7, ease: 'power3.in' }, tEnd - d - 0.02);
    tl.to(el, { clipPath: CLOSED, duration: d * 0.3, ease: 'power2.in' }, tEnd - d * 0.3 - 0.02);
  }
  // one item inside a panel arriving on its own word
  const pop = (sel, t, from = { y: 16, scale: 0.94 }) =>
    tl.fromTo(sel, { opacity: 0, ...from }, { opacity: 1, y: 0, x: 0, scale: 1, duration: 0.34, ease: 'back.out(1.6)' }, t);
  // the footage steps back behind a LARGE overlay
  function dim(t0, t1, to = 1) {
    tl.fromTo('#dim', { opacity: 0 }, { opacity: to, duration: 0.3, ease: 'power2.out' }, t0);
    tl.to('#dim', { opacity: 0, duration: 0.3, ease: 'power2.in' }, t1 - 0.3);
  }
  // highlighter stroke on a real article phrase (boxes from capture-article.mjs)
  const mark = (sel, t, d = 0.35) => tl.fromTo(sel, { scaleX: 0 }, { scaleX: 1, duration: d, ease: 'power2.inOut' }, t);
  // move the article page inside its window: scroll to a y (screenshot px) and zoom, as one gesture
  const pageTo = (sel, t, x, y, s, d = 0.9) => tl.to(sel, { x: -x * s, y: -y * s, scale: s, duration: d, ease: 'power2.inOut' }, t);
  // camera
  const camSet = (t, s = 1.0) => tl.set('#video-zoom', { scale: s }, t);
  const punch = (t, s = 1.1) => tl.to('#video-zoom', { scale: s, duration: 0.32, ease: 'power2.out' }, t);
  const creep = (t0, t1, s = 1.06) => tl.to('#video-zoom', { scale: s, duration: t1 - t0, ease: 'power1.inOut' }, t0);
  // count-up and typing: one proxy tween each (seek-safe)
  function count(sel, t, to, d = 1.1, fmt = n => Math.round(n).toLocaleString('en-US')) {
    const el = $(sel), p = { n: 0 }; el.textContent = fmt(0);
    tl.to(p, { n: to, duration: d, ease: 'power2.out', onUpdate: () => { el.textContent = fmt(p.n); } }, t);
  }
  function type(sel, t, cps = 24) {
    const el = $(sel), full = el.dataset.text || el.textContent, p = { n: 0 }; el.textContent = '';
    tl.to(p, { n: full.length, duration: full.length / cps, ease: 'none', onUpdate: () => { el.textContent = full.slice(0, Math.floor(p.n)); } }, t);
  }
  return { lgIn, lgOut, pop, dim, mark, pageTo, camSet, punch, creep, count, type };
}
