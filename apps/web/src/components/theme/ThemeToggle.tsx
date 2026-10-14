"use client";

import { Moon, Sun } from "lucide-react";

import { useTheme } from "@/components/theme/ThemeProvider";
import { cn } from "@/lib/cn";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme, mounted } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className={cn(
        "gema-theme-toggle",
        mounted && isDark && "is-dark",
        className,
      )}
      onClick={toggleTheme}
      aria-label={isDark ? "Activar modo claro" : "Activar modo oscuro"}
      aria-pressed={isDark}
      title={isDark ? "Modo claro" : "Modo oscuro"}
    >
      <span className="gema-theme-toggle-scan" aria-hidden />
      <span className="gema-theme-toggle-track-icons" aria-hidden>
        <Sun className="gema-theme-toggle-track-sun h-3 w-3" />
        <Moon className="gema-theme-toggle-track-moon h-3 w-3" />
      </span>
      <span className="gema-theme-toggle-knob">
        <Sun
          className={cn(
            "gema-theme-toggle-icon gema-theme-toggle-icon--sun h-3.5 w-3.5",
            isDark && "is-hidden",
          )}
          aria-hidden
        />
        <Moon
          className={cn(
            "gema-theme-toggle-icon gema-theme-toggle-icon--moon h-3.5 w-3.5",
            !isDark && "is-hidden",
          )}
          aria-hidden
        />
      </span>
    </button>
  );
}
