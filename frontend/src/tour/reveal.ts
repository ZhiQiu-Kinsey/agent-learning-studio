const MARGIN = 96;

const scrolls = (box: HTMLElement) =>
  /(auto|scroll|overlay)/.test(getComputedStyle(box).overflowY) &&
  box.scrollHeight > box.clientHeight;

/** Resolves when the page stops scrolling (or after a cap, if it never started). */
const settled = () =>
  new Promise<void>((resolve) => {
    const finish = () => {
      window.removeEventListener("scrollend", finish, true);
      clearTimeout(timer);
      resolve();
    };
    window.addEventListener("scrollend", finish, true);
    const timer = window.setTimeout(finish, 900);
  });

/**
 * Brings a tour target into view before it is framed: first every scrolling
 * box around `target` (e.g. a code block) puts it near its top, then the page
 * centres `frame` (the box that will be framed) or, if it is taller than the
 * screen, aligns its top below the header. Resolves once scrolling ends, so
 * the frame is drawn at its final place.
 */
export async function reveal(
  target: HTMLElement,
  frame: HTMLElement,
  smooth: boolean,
) {
  for (
    let box = target.parentElement;
    box && box !== document.body && box !== document.documentElement;
    box = box.parentElement
  ) {
    if (!scrolls(box)) continue;
    const inner = target.getBoundingClientRect();
    const outer = box.getBoundingClientRect();
    if (inner.top >= outer.top && inner.bottom <= outer.bottom) continue;
    // Inner boxes jump: the page is dimmed while a step prepares.
    box.scrollTop += inner.top - outer.top - 16;
  }
  const rect = frame.getBoundingClientRect();
  const fits = rect.height <= window.innerHeight - MARGIN * 2;
  const desired = fits ? (window.innerHeight - rect.height) / 2 : MARGIN;
  const delta = rect.top - desired;
  if (Math.abs(delta) < 4) return;
  if (fits && rect.top >= MARGIN && rect.bottom <= window.innerHeight - MARGIN)
    return;
  window.scrollTo({
    top: window.scrollY + delta,
    behavior: smooth ? "smooth" : "auto",
  });
  if (smooth) await settled();
}
