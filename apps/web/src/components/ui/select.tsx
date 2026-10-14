"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import {
  Children,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";
import { useDismissArmed } from "@/lib/use-dismiss-armed";

type SelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

type PanelPos = { top: number; left: number; width: number; maxHeight: number };

function extractText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) {
    return extractText(node.props.children);
  }
  return "";
}

function parseOptions(children: ReactNode): SelectOption[] {
  const options: SelectOption[] = [];
  Children.forEach(children, (child) => {
    if (!isValidElement<{
      value?: string | number;
      disabled?: boolean;
      label?: string;
      children?: ReactNode;
    }>(child)) {
      return;
    }
    if (child.type !== "option") return;
    const value =
      child.props.value != null ? String(child.props.value) : "";
    const label =
      child.props.label ??
      (extractText(child.props.children).trim() || value);
    options.push({
      value,
      label,
      disabled: Boolean(child.props.disabled),
    });
  });
  return options;
}

export type SelectProps = Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  "children" | "size"
> & {
  children: ReactNode;
};

export function Select({
  className,
  children,
  value,
  defaultValue,
  onChange,
  disabled = false,
  required = false,
  id,
  name,
  "aria-label": ariaLabel,
  "aria-invalid": ariaInvalid,
  "aria-describedby": ariaDescribedBy,
}: SelectProps) {
  const listboxId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const isControlled = value !== undefined;
  const [uncontrolled, setUncontrolled] = useState(
    defaultValue != null ? String(defaultValue) : "",
  );
  const current = isControlled ? String(value ?? "") : uncontrolled;
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [pos, setPos] = useState<PanelPos | null>(null);
  const dismissArmed = useDismissArmed(open);

  const options = useMemo(() => parseOptions(children), [children]);

  const selected = useMemo(
    () => options.find((o) => o.value === current) ?? null,
    [options, current],
  );

  const enabledIndexes = useMemo(
    () =>
      options
        .map((o, i) => (o.disabled ? -1 : i))
        .filter((i) => i >= 0),
    [options],
  );

  const commit = useCallback(
    (next: string) => {
      if (!isControlled) setUncontrolled(next);
      if (onChange) {
        const event = {
          target: { value: next, name: name ?? "" },
          currentTarget: { value: next, name: name ?? "" },
        } as ChangeEvent<HTMLSelectElement>;
        onChange(event);
      }
      setOpen(false);
      triggerRef.current?.focus();
    },
    [isControlled, name, onChange],
  );

  const updatePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const gap = 6;
    const spaceBelow = window.innerHeight - rect.bottom - gap - 12;
    const spaceAbove = rect.top - gap - 12;
    const preferBelow = spaceBelow >= 200 || spaceBelow >= spaceAbove;
    const maxHeight = Math.min(
      280,
      Math.max(140, preferBelow ? spaceBelow : spaceAbove),
    );
    setPos({
      top: preferBelow
        ? rect.bottom + gap
        : Math.max(8, rect.top - gap - maxHeight),
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
    const selectedIndex = Math.max(
      0,
      options.findIndex((o) => o.value === current && !o.disabled),
    );
    setHighlight(
      enabledIndexes.includes(selectedIndex)
        ? selectedIndex
        : (enabledIndexes[0] ?? 0),
    );
  }, [open, current, options, enabledIndexes]);

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

  useEffect(() => {
    if (!open) return;
    const row = listRef.current?.querySelector<HTMLElement>(
      `[data-select-index="${highlight}"]`,
    );
    if (typeof row?.scrollIntoView === "function") {
      row.scrollIntoView({ block: "nearest" });
    }
  }, [highlight, open]);

  function moveHighlight(delta: number) {
    if (!enabledIndexes.length) return;
    const posInEnabled = enabledIndexes.indexOf(highlight);
    const nextPos =
      posInEnabled < 0
        ? 0
        : (posInEnabled + delta + enabledIndexes.length) %
          enabledIndexes.length;
    setHighlight(enabledIndexes[nextPos]!);
  }

  function onTriggerKeyDown(e: ReactKeyboardEvent<HTMLButtonElement>) {
    if (disabled) return;
    if (
      e.key === "ArrowDown" ||
      e.key === "ArrowUp" ||
      e.key === "Enter" ||
      e.key === " "
    ) {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (e.key === "ArrowDown") moveHighlight(1);
      else if (e.key === "ArrowUp") moveHighlight(-1);
      else if (e.key === "Enter" || e.key === " ") {
        const option = options[highlight];
        if (option && !option.disabled) commit(option.value);
      }
    }
  }

  const panel =
    open && pos && typeof document !== "undefined"
      ? createPortal(
          <div className="gema-portal-layer" role="presentation">
            <button
              type="button"
              className="fixed inset-0 cursor-default bg-transparent"
              aria-label="Cerrar lista"
              tabIndex={dismissArmed ? 0 : -1}
              onClick={dismissArmed ? () => setOpen(false) : undefined}
            />
            <div
              id={listboxId}
              role="listbox"
              aria-label={ariaLabel}
              className="gema-select-menu"
              style={{
                top: pos.top,
                left: pos.left,
                width: pos.width,
                maxHeight: pos.maxHeight,
              }}
            >
              <div
                ref={listRef}
                className="gema-select-menu-list"
                style={{ maxHeight: pos.maxHeight }}
              >
                {options.length === 0 ? (
                  <p className="px-2.5 py-6 text-center text-sm text-muted">
                    Sin opciones
                  </p>
                ) : (
                  options.map((option, index) => {
                    const isSelected = option.value === current;
                    const isHighlighted = index === highlight;
                    return (
                      <button
                        key={`${option.value}-${index}`}
                        type="button"
                        role="option"
                        data-select-index={index}
                        aria-selected={isSelected}
                        disabled={option.disabled}
                        className={cn(
                          "gema-select-option",
                          isHighlighted && "is-highlighted",
                          isSelected && "is-selected",
                          option.disabled && "is-disabled",
                        )}
                        onMouseEnter={() => {
                          if (!option.disabled) setHighlight(index);
                        }}
                        onClick={() => {
                          if (!option.disabled) commit(option.value);
                        }}
                      >
                        <span className="min-w-0 flex-1 truncate">
                          {option.label}
                        </span>
                        {isSelected ? (
                          <Check
                            className="h-3.5 w-3.5 shrink-0 text-primary"
                            aria-hidden
                          />
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

  const placeholderLike = !selected || selected.label === "";

  return (
    <div className="relative min-w-0 w-full max-w-full">
      {name ? (
        <select
          name={name}
          value={current}
          required={required}
          disabled={disabled}
          tabIndex={-1}
          aria-hidden
          className="sr-only"
          onChange={() => undefined}
        >
          {options.map((option, index) => (
            <option
              key={`${option.value}-${index}`}
              value={option.value}
              disabled={option.disabled}
            >
              {option.label}
            </option>
          ))}
        </select>
      ) : null}
      {required && !name ? (
        <input
          tabIndex={-1}
          aria-hidden
          className="sr-only"
          value={current}
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
        aria-invalid={ariaInvalid}
        aria-describedby={ariaDescribedBy}
        className={cn(
          "select-field flex w-full max-w-full min-w-0 items-center gap-2 overflow-hidden text-left",
          open && "is-open",
          className,
        )}
        onClick={() => {
          if (disabled) return;
          setOpen((v) => !v);
        }}
        onKeyDown={onTriggerKeyDown}
      >
        <span
          className={cn(
            "min-w-0 flex-1 truncate",
            placeholderLike && !selected?.value
              ? "text-muted"
              : "text-foreground",
          )}
        >
          {selected?.label || "Seleccionar…"}
        </span>
        <ChevronsUpDown
          className="h-4 w-4 shrink-0 text-muted"
          aria-hidden
        />
      </button>
      {panel}
    </div>
  );
}
