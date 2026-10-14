let lockCount = 0;

/**
 * Nested-safe body scroll lock for overlays.
 * Do NOT set position:fixed on body — on mobile browsers that makes
 * portaled position:fixed overlays shift/vanish with scroll offset.
 */
export function lockBodyScroll() {
  if (typeof document === "undefined") return;
  lockCount += 1;
  if (lockCount === 1) {
    const scrollbar = window.innerWidth - document.documentElement.clientWidth;
    document.body.dataset.gemaScrollLock = "true";
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    document.documentElement.style.overscrollBehavior = "none";
    document.body.style.overscrollBehavior = "none";
    if (scrollbar > 0) {
      document.body.style.paddingRight = `${scrollbar}px`;
    }
  }
}

export function unlockBodyScroll() {
  if (typeof document === "undefined") return;
  lockCount = Math.max(0, lockCount - 1);
  if (lockCount === 0) {
    delete document.body.dataset.gemaScrollLock;
    document.documentElement.style.overflow = "";
    document.body.style.overflow = "";
    document.documentElement.style.overscrollBehavior = "";
    document.body.style.overscrollBehavior = "";
    document.body.style.paddingRight = "";
  }
}
