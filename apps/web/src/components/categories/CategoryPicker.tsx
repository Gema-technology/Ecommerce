"use client";

import { Check, ChevronsUpDown, Search, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { createPortal } from "react-dom";

import type { Category } from "@/lib/catalog-types";
import {
  excludeCategorySubtree,
  filterCategoryOptions,
  flattenCategories,
  getCategoryPathLabel,
  type FlatCategoryOption,
} from "@/lib/category-tree";
import { cn } from "@/lib/cn";
import { useDismissArmed } from "@/lib/use-dismiss-armed";

export type CategoryPickerProps = {
  categories: Category[];
  value: string;
  onChange: (value: string) => void;
  /** `id` for admin forms; `slug` for storefront filters. */
  valueKey?: "id" | "slug";
  id?: string;
  name?: string;
  placeholder?: string;
  emptyLabel?: string;
  searchPlaceholder?: string;
  disabled?: boolean;
  required?: boolean;
  clearable?: boolean;
  /** Hide inactive categories (default true). */
  activeOnly?: boolean;
  /** Exclude this category and its descendants (parent picker). */
  excludeSubtreeOf?: string | null;
  className?: string;
  "aria-label"?: string;
};

type PanelPos = { top: number; left: number; width: number; maxHeight: number };

function optionValue(option: FlatCategoryOption, valueKey: "id" | "slug") {
  return valueKey === "slug" ? option.slug : option.id;
}

export function CategoryPicker({
  categories,
  value,
  onChange,
  valueKey = "id",
  id,
  name,
  placeholder = "Buscar categoría…",
  emptyLabel = "Sin categoría",
  searchPlaceholder = "Nombre o ruta…",
  disabled = false,
  required = false,
  clearable = true,
  activeOnly = true,
  excludeSubtreeOf = null,
  className,
  "aria-label": ariaLabel = "Categoría",
}: CategoryPickerProps) {
  const listboxId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const [pos, setPos] = useState<PanelPos | null>(null);
  const dismissArmed = useDismissArmed(open);

  const source = useMemo(() => {
    const base = activeOnly
      ? categories.filter((c) => c.is_active)
      : categories;
    const flat = flattenCategories(base);
    return excludeCategorySubtree(flat, excludeSubtreeOf);
  }, [categories, activeOnly, excludeSubtreeOf]);

  const filtered = useMemo(
    () => filterCategoryOptions(source, query, categories),
    [source, query, categories],
  );

  const selected = useMemo(() => {
    if (!value) return null;
    return (
      source.find((o) => optionValue(o, valueKey) === value) ??
      flattenCategories(categories).find(
        (o) => optionValue(o, valueKey) === value,
      ) ??
      null
    );
  }, [value, source, valueKey, categories]);

  const selectedPath = useMemo(() => {
    if (!selected) return null;
    const cat = categories.find((c) => c.id === selected.id);
    return cat ? getCategoryPathLabel(cat, categories) : selected.name;
  }, [selected, categories]);

  const updatePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const gap = 6;
    const spaceBelow = window.innerHeight - rect.bottom - gap - 12;
    const spaceAbove = rect.top - gap - 12;
    const preferBelow = spaceBelow >= 220 || spaceBelow >= spaceAbove;
    const maxHeight = Math.min(320, Math.max(160, preferBelow ? spaceBelow : spaceAbove));
    setPos({
      top: preferBelow ? rect.bottom + gap : Math.max(8, rect.top - gap - maxHeight),
      left: rect.left,
      width: rect.width,
      maxHeight,
    });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    const onReposition = () => updatePosition();
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => searchRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  function choose(next: string) {
    onChange(next);
    setOpen(false);
    triggerRef.current?.focus();
  }

  function toggleOpen() {
    if (disabled) return;
    if (!open) {
      setQuery("");
      setHighlight(0);
      setOpen(true);
    } else {
      setOpen(false);
    }
  }

  function onSearchKeyDown(e: ReactKeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, Math.max(filtered.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const option = filtered[highlight];
      if (option) choose(optionValue(option, valueKey));
    }
  }

  useEffect(() => {
    if (!open) return;
    const row = listRef.current?.querySelector<HTMLElement>(
      `[data-cat-index="${highlight}"]`,
    );
    row?.scrollIntoView({ block: "nearest" });
  }, [highlight, open]);

  const panel =
    open && pos && typeof document !== "undefined"
      ? createPortal(
          <div className="gema-portal-layer" role="presentation">
            <button
              type="button"
              className="fixed inset-0 cursor-default bg-transparent"
              aria-label="Cerrar buscador"
              tabIndex={dismissArmed ? 0 : -1}
              onClick={dismissArmed ? () => setOpen(false) : undefined}
            />
            <div
              id={listboxId}
              role="listbox"
              aria-label={ariaLabel}
              className="fixed z-10 overflow-hidden rounded-[var(--radius-md)] border border-border bg-surface shadow-lg"
              style={{
                top: pos.top,
                left: pos.left,
                width: pos.width,
                maxHeight: pos.maxHeight,
              }}
            >
              <div className="flex items-center gap-2 border-b border-border px-3">
                <Search className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
                <input
                  ref={searchRef}
                  className="min-h-11 min-w-0 flex-1 border-0 bg-transparent py-2 text-sm text-foreground outline-none placeholder:text-muted"
                  placeholder={searchPlaceholder}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setHighlight(0);
                  }}
                  onKeyDown={onSearchKeyDown}
                  aria-autocomplete="list"
                  aria-controls={listboxId}
                />
              </div>
              <div
                ref={listRef}
                className="overflow-y-auto overscroll-contain p-1"
                style={{ maxHeight: Math.max(120, pos.maxHeight - 52) }}
              >
                {clearable ? (
                  <button
                    type="button"
                    role="option"
                    aria-selected={!value}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-[var(--radius-sm)] px-2.5 py-2 text-left text-sm",
                      !value
                        ? "bg-primary/5 font-medium text-primary"
                        : "text-secondary hover:bg-surface-hover hover:text-foreground",
                    )}
                    onClick={() => choose("")}
                  >
                    <span className="truncate">{emptyLabel}</span>
                    {!value ? (
                      <Check className="ml-auto h-3.5 w-3.5 shrink-0" aria-hidden />
                    ) : null}
                  </button>
                ) : null}

                {filtered.length === 0 ? (
                  <p className="px-2.5 py-6 text-center text-sm text-muted">
                    No hay categorías que coincidan.
                  </p>
                ) : (
                  filtered.map((option, index) => {
                    const selectedValue = optionValue(option, valueKey) === value;
                    const cat = categories.find((c) => c.id === option.id);
                    const path = cat
                      ? getCategoryPathLabel(cat, categories)
                      : option.name;
                    return (
                      <button
                        key={option.id}
                        type="button"
                        role="option"
                        data-cat-index={index}
                        aria-selected={selectedValue}
                        className={cn(
                          "flex w-full flex-col gap-0.5 rounded-[var(--radius-sm)] px-2.5 py-2 text-left",
                          index === highlight && "bg-surface-hover",
                          selectedValue && "bg-primary/5",
                        )}
                        style={{ paddingLeft: `${0.65 + option.depth * 0.75}rem` }}
                        onMouseEnter={() => setHighlight(index)}
                        onClick={() => choose(optionValue(option, valueKey))}
                      >
                        <span
                          className={cn(
                            "flex min-w-0 items-center gap-2 text-sm",
                            selectedValue
                              ? "font-semibold text-primary"
                              : "font-medium text-foreground",
                          )}
                        >
                          <span className="min-w-0 flex-1 truncate">
                            {option.name}
                          </span>
                          {selectedValue ? (
                            <Check
                              className="ml-auto h-3.5 w-3.5 shrink-0"
                              aria-hidden
                            />
                          ) : null}
                        </span>
                        {option.depth > 0 ? (
                          <span className="truncate font-mono text-[10px] text-muted">
                            {path}
                          </span>
                        ) : null}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <div className={cn("relative min-w-0", className)}>
      {name ? (
        <input
          type="hidden"
          name={name}
          value={value}
          required={required && !value}
        />
      ) : null}
      {required && !name ? (
        <input
          tabIndex={-1}
          aria-hidden
          className="sr-only"
          value={value}
          required
          onChange={() => undefined}
        />
      ) : null}
      <button
        ref={triggerRef}
        type="button"
        id={id}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={ariaLabel}
        className={cn(
          "input-field flex w-full max-w-full min-w-0 items-center gap-2 overflow-hidden text-left",
          disabled && "cursor-not-allowed opacity-60",
        )}
        onClick={toggleOpen}
      >
        <span className="min-w-0 flex-1 overflow-hidden">
          {selected ? (
            <>
              <span className="block truncate text-foreground">
                {selected.name}
              </span>
              {selected.depth > 0 && selectedPath ? (
                <span className="mt-0.5 block truncate font-mono text-[10px] text-muted">
                  {selectedPath}
                </span>
              ) : null}
            </>
          ) : (
            <span className="block truncate text-muted">{placeholder}</span>
          )}
        </span>
        <span className="flex shrink-0 items-center gap-1">
          {clearable && value ? (
            <span
              role="button"
              tabIndex={-1}
              className="inline-flex h-6 w-6 items-center justify-center text-muted hover:text-foreground"
              aria-label="Limpiar categoría"
              onClick={(e) => {
                e.stopPropagation();
                onChange("");
              }}
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </span>
          ) : null}
          <ChevronsUpDown className="h-4 w-4 text-muted" aria-hidden />
        </span>
      </button>
      {panel}
    </div>
  );
}
