"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export function SearchBar({
  initialQuery = "",
  placeholder = "Buscar productos…",
  className = "",
  id = "search-bar",
}: {
  initialQuery?: string;
  placeholder?: string;
  className?: string;
  id?: string;
}) {
  const router = useRouter();
  const [q, setQ] = useState(initialQuery);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (q.trim()) params.set("search", q.trim());
    router.push(params.toString() ? `/products?${params}` : "/products");
  }

  return (
    <form
      onSubmit={onSubmit}
      className={`flex items-center gap-2 ${className}`}
      role="search"
    >
      <label htmlFor={id} className="sr-only">
        Buscar productos
      </label>
      <input
        id={id}
        className="input-field min-w-0 flex-1"
        placeholder={placeholder}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <button type="submit" className="btn-secondary shrink-0">
        Buscar
      </button>
    </form>
  );
}
