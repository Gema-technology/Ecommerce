"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { CategoryNode } from "@/lib/category-tree";
import { countDescendants } from "@/lib/category-tree";

function TreeNode({
  node,
  activeSlug,
  openDepth,
}: {
  node: CategoryNode;
  activeSlug?: string;
  openDepth: number;
}) {
  const hasChildren = node.children.length > 0;
  const [open, setOpen] = useState(openDepth > 0);
  const isActive = activeSlug === node.slug;
  const descendantCount = hasChildren ? countDescendants(node) : 0;

  return (
    <li
      role="treeitem"
      aria-selected={isActive}
      aria-expanded={hasChildren ? open : undefined}
    >
      <div className="flex items-center gap-0.5">
        {hasChildren ? (
          <button
            type="button"
            className="inline-flex h-8 w-7 shrink-0 items-center justify-center text-muted transition hover:text-foreground"
            aria-expanded={open}
            aria-label={open ? `Contraer ${node.name}` : `Expandir ${node.name}`}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" aria-hidden />
            )}
          </button>
        ) : (
          <span className="inline-block h-8 w-7 shrink-0" aria-hidden />
        )}
        <Link
          href={`/categories/${node.slug}`}
          className={
            isActive
              ? "min-w-0 flex-1 truncate py-1.5 text-sm font-semibold text-primary"
              : "min-w-0 flex-1 truncate py-1.5 text-sm text-secondary transition hover:text-foreground"
          }
          aria-current={isActive ? "page" : undefined}
        >
          {node.name}
        </Link>
        {hasChildren ? (
          <span
            className="mr-1 shrink-0 font-mono text-[10px] tabular-nums text-muted"
            title={`${descendantCount} subcategorías`}
          >
            {descendantCount}
          </span>
        ) : null}
      </div>
      {hasChildren && open ? (
        <ul className="ml-3.5 border-l border-border pl-1" role="group">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              activeSlug={activeSlug}
              openDepth={openDepth - 1}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/** Recursive collapsible category tree — unlimited parent → child depth. */
export function CategoryTreeList({
  nodes,
  activeSlug,
  defaultOpenDepth = 2,
  className = "",
}: {
  nodes: CategoryNode[];
  activeSlug?: string;
  defaultOpenDepth?: number;
  className?: string;
}) {
  if (!nodes.length) {
    return (
      <p className="px-1 py-2 text-sm text-secondary">Sin subcategorías.</p>
    );
  }

  return (
    <ul className={`space-y-0.5 ${className}`.trim()} role="tree">
      {nodes.map((node) => (
        <TreeNode
          key={node.id}
          node={node}
          activeSlug={activeSlug}
          openDepth={defaultOpenDepth}
        />
      ))}
    </ul>
  );
}
