"use client";

type ImageUrlFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  help?: string;
  placeholder?: string;
};

/** External image URL with live preview — no file upload required. */
export function ImageUrlField({
  id,
  label,
  value,
  onChange,
  help = "Pega un enlace temporal (https://…). Más adelante se podrá subir el archivo.",
  placeholder = "https://…",
}: ImageUrlFieldProps) {
  const trimmed = value.trim();
  const showPreview = /^https?:\/\//i.test(trimmed);

  return (
    <div>
      <label className="label-field" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="input-field mt-1.5"
        type="url"
        inputMode="url"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
      />
      {help ? <p className="mt-1 text-xs text-muted">{help}</p> : null}
      {showPreview ? (
        <div className="mt-3 flex items-center gap-3 rounded-[var(--radius-md)] border border-border bg-surface-secondary p-3">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-[var(--radius-sm)] border border-border bg-surface">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={trimmed}
              alt=""
              className="max-h-full max-w-full object-contain p-1"
              onError={(e) => {
                e.currentTarget.style.opacity = "0.25";
              }}
            />
          </div>
          <p className="min-w-0 truncate font-mono text-[11px] text-secondary">
            Vista previa
          </p>
        </div>
      ) : null}
    </div>
  );
}
