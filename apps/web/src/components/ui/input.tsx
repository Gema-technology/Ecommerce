import {
  cloneElement,
  isValidElement,
  useId,
  type InputHTMLAttributes,
  type ReactElement,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";

import { cn } from "@/lib/cn";

export { Select } from "./select";
export type { SelectProps } from "./select";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("input-field", className)} {...props} />;
}

export function Label({
  className,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("label-field", className)} {...props} />;
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("textarea-field", className)} {...props} />;
}

export function Checkbox({
  className,
  label,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: ReactNode;
}) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <label className={cn("checkbox-field", className)} htmlFor={inputId}>
      <input id={inputId} type="checkbox" {...props} />
      <span>{label}</span>
    </label>
  );
}

type FormFieldProps = {
  label?: ReactNode;
  htmlFor?: string;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  className?: string;
  children: ReactElement;
};

export function FormField({
  label,
  htmlFor,
  hint,
  error,
  required,
  className,
  children,
}: FormFieldProps) {
  const generatedId = useId();
  const childProps = isValidElement(children)
    ? (children.props as { id?: unknown; className?: string })
    : null;
  const controlId =
    htmlFor ??
    (childProps && typeof childProps.id === "string"
      ? childProps.id
      : generatedId);
  const errorId = error ? `${controlId}-error` : undefined;
  const hintId = hint && !error ? `${controlId}-hint` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;

  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id: controlId,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy,
        className: cn(childProps?.className, error ? "is-error" : undefined),
      })
    : children;

  return (
    <div className={cn("form-field", className)}>
      {label ? (
        <Label htmlFor={controlId}>
          {label}
          {required ? <span className="label-required"> *</span> : null}
        </Label>
      ) : null}
      {control}
      {hint && !error ? (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
