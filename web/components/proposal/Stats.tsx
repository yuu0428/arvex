import { ReactNode } from "react";

type StatsProps = {
  children: ReactNode;
};

/**
 * Stat のレイアウトコンテナ。
 */
export function Stats({ children }: StatsProps) {
  return <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-8">{children}</div>;
}

type StatProps = {
  value: string;
  label: string;
  description?: string;
};

/**
 * 数字 + ラベル。Stats 内で使う。
 */
export function Stat({ value, label, description }: StatProps) {
  return (
    <div>
      <p className="text-4xl sm:text-6xl font-bold leading-none mb-3">{value}</p>
      <p className="text-sm font-medium">{label}</p>
      {description && <p className="text-xs opacity-70 mt-2 leading-relaxed">{description}</p>}
    </div>
  );
}
