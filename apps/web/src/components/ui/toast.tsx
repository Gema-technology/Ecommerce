"use client";

import { X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/cn";

type ToastTone = "success" | "error" | "warning" | "info";

type ToastItem = {
  id: string;
  message: string;
  tone: ToastTone;
};

type ToastHelpers = {
  push: (message: string, tone?: ToastTone) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastHelpers | null>(null);

const NOOP_TOAST: ToastHelpers = {
  push: () => {
    /* no-op outside provider */
  },
  success: () => {},
  error: () => {},
  warning: () => {},
  info: () => {},
};

export function useToast(): ToastHelpers {
  return useContext(ToastContext) ?? NOOP_TOAST;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((message: string, tone: ToastTone = "info") => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setItems((prev) => [...prev, { id, message, tone }]);
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  const value = useMemo<ToastHelpers>(
    () => ({
      push,
      success: (message: string) => push(message, "success"),
      error: (message: string) => push(message, "error"),
      warning: (message: string) => push(message, "warning"),
      info: (message: string) => push(message, "info"),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-3 bottom-3 z-[80] flex flex-col gap-2 sm:inset-x-auto sm:right-4 sm:bottom-4 sm:w-96"
        aria-live="polite"
      >
        {items.map((item) => (
          <div
            key={item.id}
            className={cn(
              "gema-toast pointer-events-auto animate-slide-up flex items-start justify-between gap-3",
              item.tone === "success" && "border-success/40",
              item.tone === "error" && "border-error/40",
              item.tone === "warning" && "border-warning/40",
              item.tone === "info" && "border-cyan/30",
            )}
            role="status"
          >
            <p className="min-w-0 flex-1 break-words">{item.message}</p>
            <button
              type="button"
              className="btn-ghost btn-icon btn-sm"
              aria-label="Cerrar"
              onClick={() =>
                setItems((prev) => prev.filter((t) => t.id !== item.id))
              }
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
