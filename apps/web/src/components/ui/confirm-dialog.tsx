"use client";

import {
  useCallback,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Button } from "./button";
import { Modal } from "./modal";

export type ConfirmTone = "danger" | "default";

export type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmTone;
  loading?: boolean;
  onConfirm: () => void | Promise<void>;
  onClose: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  tone = "default",
  loading = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} title={title} onClose={loading ? () => {} : onClose}>
      {description ? (
        <p className="text-sm text-muted">{description}</p>
      ) : null}
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <Button
          type="button"
          variant="ghost"
          disabled={loading}
          onClick={onClose}
        >
          {cancelLabel}
        </Button>
        <Button
          type="button"
          variant={tone === "danger" ? "danger" : "primary"}
          loading={loading}
          onClick={() => void onConfirm()}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

export type ConfirmRequest = {
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmTone;
};

type PendingConfirm = ConfirmRequest & {
  resolve: (value: boolean) => void;
};

/**
 * Imperative confirm helper — returns a promise that resolves true/false.
 * Render `{dialog}` once in the page tree.
 */
export function useConfirmDialog() {
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const pendingRef = useRef<PendingConfirm | null>(null);

  const close = useCallback((result: boolean) => {
    const current = pendingRef.current;
    pendingRef.current = null;
    setPending(null);
    current?.resolve(result);
  }, []);

  const confirm = useCallback((request: ConfirmRequest) => {
    return new Promise<boolean>((resolve) => {
      const next: PendingConfirm = { ...request, resolve };
      pendingRef.current = next;
      setPending(next);
    });
  }, []);

  const dialog = pending ? (
    <ConfirmDialog
      open
      title={pending.title}
      description={pending.description}
      confirmLabel={pending.confirmLabel}
      cancelLabel={pending.cancelLabel}
      tone={pending.tone}
      onConfirm={() => close(true)}
      onClose={() => close(false)}
    />
  ) : null;

  return { confirm, dialog };
}
