type AudienceCTAProps = {
  audience: string;
  description?: string;
  label: string;
  href: string;
};

/**
 * 相手別 CTA。複数をグリッドで並べると「誰向け」が明示される構成になる。
 */
export function AudienceCTA({ audience, description, label, href }: AudienceCTAProps) {
  return (
    <div
      className="p-8 rounded-2xl flex flex-col"
      style={{
        background: "color-mix(in srgb, var(--color-primary) 4%, transparent)",
        border: "1px solid color-mix(in srgb, var(--color-primary) 10%, transparent)",
      }}
    >
      <h3 className="text-lg font-bold mb-3">{audience}</h3>
      {description && <p className="text-sm opacity-80 leading-relaxed mb-6 flex-1">{description}</p>}
      <a
        href={href}
        className="inline-block w-fit px-6 py-3 rounded-full text-sm font-medium transition hover:opacity-90"
        style={{ background: "var(--color-primary)", color: "var(--color-neutral)" }}
      >
        {label}
      </a>
    </div>
  );
}
