"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import {
  FieldRow,
  FormModal,
  FormModalActions,
  FormSection,
} from "@/components/admin/forms/AdminFormPrimitives";
import { FormField, Input } from "@/components/ui/input";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { inventoryApi, type Location } from "@/lib/inventory-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

const LOCATION_FORM_ID = "location-form";

export default function AdminInventoryLocationsPage() {
  const list = useAdminListParams();

  const [items, setItems] = useState<Location[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [city, setCity] = useState("");
  const [province, setProvince] = useState("");
  const [country, setCountry] = useState("Ecuador");
  const [description, setDescription] = useState("");

  const [draftQ, setDraftQ] = useState(list.q);

  useEffect(() => {
    setDraftQ(list.q);
  }, [list.q]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await inventoryApi.listLocations({
        page: list.page,
        page_size: list.pageSize,
        q: list.q || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Error al cargar ubicaciones",
      );
      setItems([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, list.q]);

  useEffect(() => {
    void load();
  }, [load]);

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({ q: draftQ });
  }

  function openCreate() {
    setName("");
    setCode("");
    setCity("");
    setProvince("");
    setCountry("Ecuador");
    setDescription("");
    setError(null);
    setModalOpen(true);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await inventoryApi.createLocation({
        name,
        code,
        city: city.trim() || null,
        province: province.trim() || null,
        country: country.trim() || "Ecuador",
        description: description.trim() || null,
      });
      setModalOpen(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AdminShell title="Ubicaciones">
      <div className="mb-4">
        <Link href="/admin/inventory" className="btn-ghost btn-sm mb-2">
          ← Volver a inventario
        </Link>
        <p className="text-sm text-secondary">
          Bodegas y puntos de stock. El checkout usa la ubicación MAIN por
          defecto.
        </p>
      </div>

      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftQ("");
          list.clearFilters(["q"]);
        }}
        actions={
          <button type="button" className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" aria-hidden />
            Nueva ubicación
          </button>
        }
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Nombre o código"
          />
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={6}
        loading={loading}
        error={error}
        isEmpty={!items.length}
        emptyMessage="No hay ubicaciones."
        meta={`${total} ubicación${total === 1 ? "" : "es"}`}
        head={
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Ciudad</th>
            <th>Provincia</th>
            <th>País</th>
            <th>Estado</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/inventory/locations"
          />
        }
      >
        {items.map((loc) => (
          <tr key={loc.id}>
            <td className="font-mono text-xs">{loc.code}</td>
            <td>
              {loc.name}
              {loc.code === "MAIN" ? (
                <span className="ml-2 text-xs text-muted">
                  default checkout
                </span>
              ) : null}
            </td>
            <td>{loc.city ?? "—"}</td>
            <td>{loc.province ?? "—"}</td>
            <td>{loc.country}</td>
            <td>{loc.is_active ? "Activa" : "Inactiva"}</td>
          </tr>
        ))}
      </AdminTable>

      <FormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Nueva ubicación"
        subtitle="Código único (ej. BODEGA-2)"
        footer={
          <FormModalActions
            formId={LOCATION_FORM_ID}
            submitLabel="Crear ubicación"
            saving={saving}
            onCancel={() => setModalOpen(false)}
          />
        }
      >
        <form
          id={LOCATION_FORM_ID}
          className="admin-form"
          onSubmit={(e) => void onSubmit(e)}
        >
          <FormSection label="Datos">
            <FieldRow>
              <div>
                <label className="label-field" htmlFor="loc-name">
                  Nombre
                </label>
                <input
                  id="loc-name"
                  className="input-field"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="label-field" htmlFor="loc-code">
                  Código
                </label>
                <input
                  id="loc-code"
                  className="input-field mono-input"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="BODEGA-2"
                  required
                />
              </div>
            </FieldRow>
            <FieldRow>
              <div>
                <label className="label-field" htmlFor="loc-city">
                  Ciudad
                </label>
                <input
                  id="loc-city"
                  className="input-field"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                />
              </div>
              <div>
                <label className="label-field" htmlFor="loc-province">
                  Provincia
                </label>
                <input
                  id="loc-province"
                  className="input-field"
                  value={province}
                  onChange={(e) => setProvince(e.target.value)}
                />
              </div>
            </FieldRow>
            <div>
              <label className="label-field" htmlFor="loc-country">
                País
              </label>
              <input
                id="loc-country"
                className="input-field"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
              />
            </div>
            <div>
              <label className="label-field" htmlFor="loc-desc">
                Descripción
              </label>
              <input
                id="loc-desc"
                className="input-field"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </FormSection>
        </form>
      </FormModal>
    </AdminShell>
  );
}
