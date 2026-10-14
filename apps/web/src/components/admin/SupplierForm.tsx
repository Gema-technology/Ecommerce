"use client";

import { FormEvent, useEffect, useState } from "react";

import { FieldRow, FormSection } from "@/components/admin/forms/AdminFormPrimitives";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/auth-api";
import { suppliersApi, type Supplier, type TaxIdType } from "@/lib/suppliers-api";

export const SUPPLIER_FORM_ID = "supplier-form";

export type SupplierFormValues = {
  business_name: string;
  commercial_name: string;
  tax_id: string;
  tax_id_type: TaxIdType;
  email: string;
  phone: string;
  website_url: string;
  address: string;
  city: string;
  province: string;
  country: string;
  contact_name: string;
  notes: string;
};

export const DEFAULT_SUPPLIER_FORM: SupplierFormValues = {
  business_name: "",
  commercial_name: "",
  tax_id: "",
  tax_id_type: "RUC",
  email: "",
  phone: "",
  website_url: "",
  address: "",
  city: "",
  province: "",
  country: "Ecuador",
  contact_name: "",
  notes: "",
};

export function supplierToForm(supplier: Supplier): SupplierFormValues {
  return {
    business_name: supplier.business_name,
    commercial_name: supplier.commercial_name ?? "",
    tax_id: supplier.tax_id,
    tax_id_type: supplier.tax_id_type,
    email: supplier.email ?? "",
    phone: supplier.phone ?? "",
    website_url: supplier.website_url ?? "",
    address: supplier.address ?? "",
    city: supplier.city ?? "",
    province: supplier.province ?? "",
    country: supplier.country,
    contact_name: supplier.contact_name ?? "",
    notes: supplier.notes ?? "",
  };
}

function toPayload(form: SupplierFormValues) {
  return {
    business_name: form.business_name,
    commercial_name: form.commercial_name || null,
    tax_id: form.tax_id,
    tax_id_type: form.tax_id_type,
    email: form.email || null,
    phone: form.phone || null,
    website_url: form.website_url || null,
    address: form.address || null,
    city: form.city || null,
    province: form.province || null,
    country: form.country || "Ecuador",
    contact_name: form.contact_name || null,
    notes: form.notes || null,
  };
}

export function SupplierForm({
  supplier,
  onSuccess,
  onError,
  onSavingChange,
}: {
  supplier?: Supplier | null;
  onSuccess: (saved: Supplier) => void;
  onError?: (message: string) => void;
  onSavingChange?: (saving: boolean) => void;
}) {
  const [form, setForm] = useState<SupplierFormValues>(DEFAULT_SUPPLIER_FORM);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(supplier ? supplierToForm(supplier) : DEFAULT_SUPPLIER_FORM);
    setError(null);
  }, [supplier]);

  function setField<K extends keyof SupplierFormValues>(key: K, value: SupplierFormValues[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    onSavingChange?.(true);
    try {
      const payload = toPayload(form);
      const saved = supplier
        ? await suppliersApi.update(supplier.id, payload)
        : await suppliersApi.create(payload);
      onSuccess(saved);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "No se pudo guardar";
      setError(message);
      onError?.(message);
    } finally {
      onSavingChange?.(false);
    }
  }

  return (
    <form id={SUPPLIER_FORM_ID} className="admin-form" onSubmit={(e) => void onSubmit(e)}>
      <FormSection label="Identificación">
        <div>
          <label className="label-field" htmlFor="supplier-business_name">
            Razón social
          </label>
          <input
            id="supplier-business_name"
            className="input-field"
            value={form.business_name}
            required
            onChange={(e) => setField("business_name", e.target.value)}
          />
        </div>
        <div>
          <label className="label-field" htmlFor="supplier-commercial_name">
            Nombre comercial
          </label>
          <input
            id="supplier-commercial_name"
            className="input-field"
            value={form.commercial_name}
            onChange={(e) => setField("commercial_name", e.target.value)}
          />
        </div>
        <FieldRow>
          <div>
            <label className="label-field" htmlFor="supplier-tax_id_type">
              Tipo de ID fiscal
            </label>
            <Select
              id="supplier-tax_id_type"
              value={form.tax_id_type}
              onChange={(e) => setField("tax_id_type", e.target.value as TaxIdType)}
            >
              <option value="RUC">RUC</option>
              <option value="CEDULA">Cédula</option>
              <option value="PASSPORT">Pasaporte</option>
              <option value="OTHER">Otro</option>
            </Select>
          </div>
          <div>
            <label className="label-field" htmlFor="supplier-tax_id">
              Tax ID
            </label>
            <input
              id="supplier-tax_id"
              className="input-field"
              value={form.tax_id}
              required
              onChange={(e) => setField("tax_id", e.target.value)}
            />
          </div>
        </FieldRow>
      </FormSection>

      <FormSection label="Contacto">
        <FieldRow>
          <div>
            <label className="label-field" htmlFor="supplier-email">
              Correo
            </label>
            <input
              id="supplier-email"
              type="email"
              className="input-field"
              value={form.email}
              onChange={(e) => setField("email", e.target.value)}
            />
          </div>
          <div>
            <label className="label-field" htmlFor="supplier-phone">
              Teléfono
            </label>
            <input
              id="supplier-phone"
              className="input-field"
              value={form.phone}
              onChange={(e) => setField("phone", e.target.value)}
            />
          </div>
        </FieldRow>
        <div>
          <label className="label-field" htmlFor="supplier-website_url">
            Website
          </label>
          <input
            id="supplier-website_url"
            className="input-field"
            value={form.website_url}
            onChange={(e) => setField("website_url", e.target.value)}
          />
        </div>
        <div>
          <label className="label-field" htmlFor="supplier-contact_name">
            Contacto
          </label>
          <input
            id="supplier-contact_name"
            className="input-field"
            value={form.contact_name}
            onChange={(e) => setField("contact_name", e.target.value)}
          />
        </div>
      </FormSection>

      <FormSection label="Ubicación">
        <div>
          <label className="label-field" htmlFor="supplier-address">
            Dirección
          </label>
          <input
            id="supplier-address"
            className="input-field"
            value={form.address}
            onChange={(e) => setField("address", e.target.value)}
          />
        </div>
        <FieldRow className="sm:grid-cols-3">
          <div>
            <label className="label-field" htmlFor="supplier-city">
              Ciudad
            </label>
            <input
              id="supplier-city"
              className="input-field"
              value={form.city}
              onChange={(e) => setField("city", e.target.value)}
            />
          </div>
          <div>
            <label className="label-field" htmlFor="supplier-province">
              Provincia
            </label>
            <input
              id="supplier-province"
              className="input-field"
              value={form.province}
              onChange={(e) => setField("province", e.target.value)}
            />
          </div>
          <div>
            <label className="label-field" htmlFor="supplier-country">
              País
            </label>
            <input
              id="supplier-country"
              className="input-field"
              value={form.country}
              onChange={(e) => setField("country", e.target.value)}
            />
          </div>
        </FieldRow>
      </FormSection>

      <FormSection label="Notas">
        <textarea
          id="supplier-notes"
          className="textarea-field"
          value={form.notes}
          onChange={(e) => setField("notes", e.target.value)}
        />
      </FormSection>

      {error ? (
        <p className="text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  );
}
