import { ReactNode } from "react";

type FAQProps = {
  children?: ReactNode;
};

/**
 * FAQ コンテナ。<FAQItem q a /> を children として並べる。
 */
export function FAQ({ children }: FAQProps) {
  return <div className="space-y-3">{children}</div>;
}

type FAQItemProps = {
  q: string;
  a: string;
};

export function FAQItem({ q, a }: FAQItemProps) {
  return (
    <details
      className="group border rounded-xl overflow-hidden"
      style={{
        borderColor: "color-mix(in srgb, var(--color-primary) 15%, transparent)",
      }}
    >
      <summary className="cursor-pointer list-none flex items-center justify-between p-5 font-medium">
        <span>{q}</span>
        <span className="transition group-open:rotate-180 opacity-60">▾</span>
      </summary>
      <div className="px-5 pb-5 opacity-85 leading-relaxed">{a}</div>
    </details>
  );
}
