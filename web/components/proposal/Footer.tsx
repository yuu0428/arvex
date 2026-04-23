import { ReactNode } from "react";

type FooterProps = {
  brand: string;
  logo?: string;
  logoAlt?: string;
  children?: ReactNode;
};

/**
 * ページ末尾のフッター。brand + 任意の logo + children に <FooterLine> / <FooterLink>。
 */
export function Footer({ brand, logo, logoAlt, children }: FooterProps) {
  return (
    <footer
      className="px-6 sm:px-10 lg:px-16 py-12 text-sm"
      style={{
        borderTop: "1px solid color-mix(in srgb, var(--color-primary) 10%, transparent)",
      }}
    >
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row sm:items-start justify-between gap-6">
        <div className="flex items-start gap-3">
          {logo && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logo}
              alt={logoAlt || brand}
              className="w-10 h-10 rounded-full object-cover"
            />
          )}
          <div>
            <p className="font-bold text-base mb-2">{brand}</p>
            <div className="text-xs opacity-70 space-y-1">{children}</div>
          </div>
        </div>
      </div>
    </footer>
  );
}

export function FooterLine({ children }: { children?: ReactNode }) {
  return <p>{children}</p>;
}

export function FooterLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="no-underline opacity-70 hover:opacity-100 transition mr-4"
      style={{ color: "inherit" }}
    >
      {label}
    </a>
  );
}
