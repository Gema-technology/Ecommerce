"use client";

import { useEffect, useState } from "react";

/** Ignore dismiss taps for a short window after open (mobile ghost-click). */
export function useDismissArmed(open: boolean, delayMs = 400) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => setArmed(true), delayMs);
    return () => {
      window.clearTimeout(id);
      setArmed(false);
    };
  }, [open, delayMs]);

  return open && armed;
}
