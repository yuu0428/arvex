import { ReactNode } from "react";

type GridProps = {
  cols?: 2 | 3 | 4;
  gap?: "sm" | "md" | "lg";
  children: ReactNode;
};

/**
 * レスポンシブな CSS Grid。モバイル1カラム → 指定数。
 */
export function Grid({ cols = 3, gap = "md", children }: GridProps) {
  const colClass = cols === 2 ? "sm:grid-cols-2" : cols === 4 ? "sm:grid-cols-2 lg:grid-cols-4" : "sm:grid-cols-2 lg:grid-cols-3";
  const gapClass = gap === "sm" ? "gap-4" : gap === "lg" ? "gap-10" : "gap-6";
  return <div className={`grid grid-cols-1 ${colClass} ${gapClass}`}>{children}</div>;
}
