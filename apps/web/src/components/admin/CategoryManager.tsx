"use client";

import {
  ChevronDown,
  ChevronRight,
  FolderPlus,
  FolderTree,
  Pencil,
  Plus,
  Search,
  Tag,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CategoryForm, CATEGORY_FORM_ID } from "@/components/admin/CategoryForm";
import {
  FormModal,
  FormModalActions,
} from "@/components/admin/forms/AdminFormPrimitives";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/auth-api";
import { catalogApi, type Category } from "@/lib/catalog-api";
import {
  buildCategoryForest,
  getCategoryAncestors,
  type CategoryNode,
} from "@/lib/category-tree";
import { cn } from "@/lib/cn";

function pathLabel(category: Category, items: Category[]): string {
  const ancestors = getCategoryAncestors(category, items);
  return [...ancestors.map((a) => a.name), category.name].join(" / ");
}

function AdminTreeNode({
  node,
  selectedId,
  expanded,
  onToggle,
  onSelect,
  onEdit,
  onAddChild,
  query,
}: {
  node: CategoryNode;
  selectedId: string | null;
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onSelect: (id: string) => void;
  onEdit: (id: string) => void;
  onAddChild: (parentId: string) => void;
  query: string;
}) {
  const hasChildren = node.children.length > 0;
  const isOpen = expanded.has(node.id);
  const selected = selectedId === node.id;
  const q = query.trim().toLowerCase();
  const selfMatch = !q || node.name.toLowerCase().includes(q);

  function anyMatch(n: CategoryNode): boolean {
    if (n.name.toLowerCase().includes(q)) return true;
    return n.children.some(anyMatch);
  }
  const childMatches = !q || node.children.some(anyMatch);

  if (!selfMatch && !childMatches) return null;

  return (
    <li>
      <div
        className={cn(
          "group flex items-center gap-0.5 rounded-[var(--radius-md)] pr-1",
          selected && "bg-primary/5",
        )}
      >
        {hasChildren ? (
          <button
            type="button"
            className="inline-flex h-8 w-7 shrink-0 items-center justify-center text-muted hover:text-foreground"
            aria-expanded={isOpen}
            aria-label={isOpen ? `Contraer ${node.name}` : `Expandir ${node.name}`}
            onClick={() => onToggle(node.id)}
          >
            {isOpen ? (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" aria-hidden />
            )}
          </button>
        ) : (
          <span className="inline-block h-8 w-7 shrink-0" aria-hidden />
        )}
        <button
          type="button"
          onClick={() => onSelect(node.id)}
          onDoubleClick={() => onEdit(node.id)}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-2 py-1.5 text-left text-sm",
            selected
              ? "font-semibold text-primary"
              : "text-secondary hover:text-foreground",
            !node.is_active && "opacity-50",
          )}
        >
          <Tag className="h-3.5 w-3.5 shrink-0 opacity-50" aria-hidden />
          <span className="truncate">{node.name}</span>
          {!node.is_active ? (
            <span className="shrink-0 font-mono text-[10px] text-muted">
              OFF
            </span>
          ) : null}
          {hasChildren ? (
            <span className="ml-auto shrink-0 font-mono text-[10px] text-muted">
              {node.children.length}
            </span>
          ) : null}
        </button>
        <button
          type="button"
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center text-muted opacity-0 transition group-hover:opacity-100 hover:text-primary focus-visible:opacity-100"
          title={`Editar ${node.name}`}
          aria-label={`Editar ${node.name}`}
          onClick={() => onEdit(node.id)}
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden />
        </button>
        <button
          type="button"
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center text-muted opacity-0 transition group-hover:opacity-100 hover:text-primary focus-visible:opacity-100"
          title={`Agregar subcategoría bajo ${node.name}`}
          aria-label={`Agregar subcategoría bajo ${node.name}`}
          onClick={() => onAddChild(node.id)}
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
      {hasChildren && isOpen ? (
        <ul className="ml-3 border-l border-border pl-1">
          {node.children.map((child) => (
            <AdminTreeNode
              key={child.id}
              node={child}
              selectedId={selectedId}
              expanded={expanded}
              onToggle={onToggle}
              onSelect={onSelect}
              onEdit={onEdit}
              onAddChild={onAddChild}
              query={query}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function CategoryManager() {
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [items, setItems] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [defaultParentId, setDefaultParentId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const forest = useMemo(() => buildCategoryForest(items), [items]);
  const selected = selectedId
    ? (items.find((c) => c.id === selectedId) ?? null)
    : null;

  const load = useCallback(async (preferExpandId?: string | null) => {
    setLoading(true);
    try {
      const data = await catalogApi.listCategories(true);
      setItems(data);
      setExpanded((prev) => {
        const next = new Set(prev);
        if (prev.size === 0) {
          for (const c of data.filter((x) => !x.parent_id)) next.add(c.id);
        }
        if (preferExpandId) {
          const byId = new Map(data.map((c) => [c.id, c]));
          let cur = byId.get(preferExpandId);
          while (cur?.parent_id) {
            next.add(cur.parent_id);
            cur = byId.get(cur.parent_id);
          }
        }
        return next;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const q = query.trim().toLowerCase();
    if (!q) return;
    const byId = new Map(items.map((c) => [c.id, c]));
    const next = new Set<string>();
    for (const cat of items) {
      if (!cat.name.toLowerCase().includes(q)) continue;
      let cur: Category | undefined = cat;
      while (cur?.parent_id) {
        next.add(cur.parent_id);
        cur = byId.get(cur.parent_id);
      }
    }
    if (next.size) setExpanded((prev) => new Set([...prev, ...next]));
  }, [query, items]);

  function openCreateRoot() {
    setEditing(null);
    setDefaultParentId(null);
    setModalOpen(true);
  }

  function openCreateChild(parentId: string) {
    setExpanded((prev) => new Set(prev).add(parentId));
    setSelectedId(parentId);
    setEditing(null);
    setDefaultParentId(parentId);
    setModalOpen(true);
  }

  function openEdit(categoryId: string) {
    const cat = items.find((c) => c.id === categoryId);
    if (!cat) return;
    setSelectedId(categoryId);
    setEditing(cat);
    setDefaultParentId(null);
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditing(null);
    setDefaultParentId(null);
  }

  async function toggleActive(category: Category) {
    if (category.is_active) {
      const ok = await confirm({
        title: "Desactivar categoría",
        description: `¿Desactivar «${category.name}»?`,
        confirmLabel: "Desactivar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setError(null);
    try {
      if (category.is_active) {
        await catalogApi.deleteCategory(category.id);
        toast.success("Categoría desactivada.");
      } else {
        await catalogApi.updateCategory(category.id, { is_active: true });
        toast.success("Categoría activada.");
      }
      await load(category.id);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo actualizar";
      setError(msg);
      toast.error(msg);
    }
  }

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const createParent = defaultParentId
    ? (items.find((c) => c.id === defaultParentId) ?? null)
    : null;

  const modalSubtitle = editing
    ? pathLabel(editing, items)
    : createParent
      ? `Subcategoría de ${pathLabel(createParent, items)}`
      : "Categoría raíz — se generará el slug al guardar";

  return (
    <div className="space-y-4">
      {confirmDialog}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="max-w-2xl text-sm text-secondary">
            Navega el árbol, usa el lápiz para editar o{" "}
            <span className="font-medium text-foreground">+</span> para crear
            una hija. El formulario se abre en el mismo modal del resto del
            admin.
          </p>
          <p className="mt-1 font-mono text-xs text-muted">
            {forest.length} familia{forest.length === 1 ? "" : "s"} ·{" "}
            {items.length} categoría{items.length === 1 ? "" : "s"}
          </p>
        </div>
        <button
          type="button"
          className="btn-primary inline-flex items-center gap-2"
          onClick={openCreateRoot}
        >
          <FolderPlus className="h-4 w-4" aria-hidden />
          Nueva categoría raíz
        </button>
      </div>

      {error ? (
        <p className="text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(16rem,24rem)_1fr] lg:items-start">
        <section className="gema-panel-elevated overflow-hidden">
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <FolderTree className="h-4 w-4 text-primary" aria-hidden />
                <h2 className="font-display text-sm font-semibold text-navy">
                  Árbol
                </h2>
              </div>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => setExpanded(new Set(items.map((c) => c.id)))}
                >
                  Expandir
                </button>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => setExpanded(new Set())}
                >
                  Contraer
                </button>
              </div>
            </div>
            <label className="mt-3 flex w-full min-w-0 items-center gap-2 rounded-[var(--radius-md)] border border-border bg-surface px-3 focus-within:border-primary focus-within:shadow-[0_0_0_3px_color-mix(in_srgb,var(--gema-primary)_18%,transparent)]">
              <Search
                className="h-3.5 w-3.5 shrink-0 text-muted"
                aria-hidden
              />
              <input
                className="min-h-[46px] w-full min-w-0 flex-1 border-0 bg-transparent py-2 text-sm text-foreground outline-none placeholder:text-muted"
                placeholder="Buscar categoría…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Buscar categoría"
              />
            </label>
          </div>

          <div className="max-h-[min(70vh,36rem)] overflow-y-auto px-2 py-2">
            {loading ? (
              <p className="px-2 py-6 text-sm text-secondary">Cargando…</p>
            ) : null}
            {!loading && forest.length === 0 ? (
              <div className="px-3 py-8 text-center">
                <p className="text-sm text-secondary">Aún no hay categorías.</p>
                <button
                  type="button"
                  className="btn-primary mt-4"
                  onClick={openCreateRoot}
                >
                  Crear la primera
                </button>
              </div>
            ) : null}
            {!loading && forest.length > 0 ? (
              <ul className="space-y-0.5" role="tree">
                {forest.map((node) => (
                  <AdminTreeNode
                    key={node.id}
                    node={node}
                    selectedId={selectedId}
                    expanded={expanded}
                    onToggle={toggleExpand}
                    onSelect={setSelectedId}
                    onEdit={openEdit}
                    onAddChild={openCreateChild}
                    query={query}
                  />
                ))}
              </ul>
            ) : null}
          </div>
        </section>

        <section className="gema-panel-elevated min-h-[14rem] p-5 sm:p-6">
          {selected ? (
            <div className="space-y-4">
              <div className="flex items-start gap-4">
                {selected.image_url ? (
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-[var(--radius-sm)] border border-border bg-surface-secondary">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={selected.image_url}
                      alt=""
                      className="max-h-full max-w-full object-contain p-1.5"
                    />
                  </div>
                ) : (
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-border bg-surface-secondary font-mono text-sm text-muted">
                    {selected.name.slice(0, 2).toUpperCase()}
                  </div>
                )}
                <div className="min-w-0">
                  <p className="font-mono text-[10px] tracking-wider text-muted">
                    SELECCIONADA
                  </p>
                  <h2 className="mt-1 font-display text-xl font-semibold text-navy">
                    {selected.name}
                  </h2>
                  <p className="mt-1 text-sm text-secondary">
                    {pathLabel(selected, items)}
                  </p>
                  <p className="mt-1 font-mono text-xs text-muted">
                    {selected.slug}
                    {" · "}
                    {selected.is_active ? (
                      <span className="text-success">Activa</span>
                    ) : (
                      <span className="text-warning">Inactiva</span>
                    )}
                  </p>
                </div>
              </div>
              {selected.description ? (
                <p className="text-sm text-secondary">{selected.description}</p>
              ) : null}
              <div className="flex flex-wrap gap-2 border-t border-border pt-4">
                <button
                  type="button"
                  className="btn-primary inline-flex items-center gap-2"
                  onClick={() => openEdit(selected.id)}
                >
                  <Pencil className="h-4 w-4" aria-hidden />
                  Editar
                </button>
                <button
                  type="button"
                  className="btn-ghost inline-flex items-center gap-2"
                  onClick={() => openCreateChild(selected.id)}
                >
                  <Plus className="h-4 w-4" aria-hidden />
                  Agregar hija
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => void toggleActive(selected)}
                >
                  {selected.is_active ? "Desactivar" : "Activar"}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex h-full min-h-[12rem] flex-col items-center justify-center text-center">
              <FolderTree className="h-9 w-9 text-muted/40" aria-hidden />
              <p className="mt-3 text-sm text-secondary">
                Selecciona una categoría en el árbol para ver su resumen, o
                crea una nueva con el botón de arriba.
              </p>
            </div>
          )}
        </section>
      </div>

      <FormModal
        open={modalOpen}
        onClose={closeModal}
        title={editing ? "Editar categoría" : "Nueva categoría"}
        subtitle={modalSubtitle}
        footer={
          <FormModalActions
            formId={CATEGORY_FORM_ID}
            submitLabel={editing ? "Guardar cambios" : "Crear categoría"}
            saving={saving}
            onCancel={closeModal}
          />
        }
      >
        <CategoryForm
          key={editing?.id ?? `new-${defaultParentId ?? "root"}`}
          category={editing}
          categories={items}
          defaultParentId={defaultParentId}
          onSavingChange={setSaving}
          onSuccess={() => {
            const keepParent = defaultParentId;
            closeModal();
            void load(editing?.id ?? keepParent);
          }}
        />
      </FormModal>
    </div>
  );
}
