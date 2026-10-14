import type { FlatCategoryOption } from "@/lib/category-tree";

/** Indented `<option>` list for deep category hierarchies. */
export function CategorySelectOptions({
  options,
  valueKey = "slug",
}: {
  options: FlatCategoryOption[];
  valueKey?: "slug" | "id";
}) {
  return (
    <>
      {options.map((option) => (
        <option key={option.id} value={valueKey === "id" ? option.id : option.slug}>
          {option.label}
        </option>
      ))}
    </>
  );
}
