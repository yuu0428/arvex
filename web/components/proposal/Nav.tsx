import { ReactNode } from "react";

type NavProps = {
  brand: string;
  children?: ReactNode;
};

/**
 * 上部のナビ。children に <NavItem> を並べる。
 */
export function Nav({ brand, children }: NavProps) {
  return (
    <nav
      className="sticky top-0 z-10 px-6 sm:px-10 lg:px-16 py-4 flex items-center justify-between backdrop-blur"
      style={{
        background: "color-mix(in srgb, var(--color-neutral) 85%, transparent)",
        borderBottom: "1px solid color-mix(in srgb, var(--color-primary) 10%, transparent)",
      }}
    >
      <a
        href="#"
        className="font-bold text-base sm:text-lg no-underline"
        style={{ color: "var(--color-primary)" }}
      >
        {brand}
      </a>
      {children && (
        <ul className="hidden sm:flex items-center gap-6 text-sm list-none m-0 p-0">
          {children}
        </ul>
      )}
    </nav>
  );
}

type NavItemProps = {
  href: string;
  label: string;
};

export function NavItem({ href, label }: NavItemProps) {
  return (
    <li className="m-0">
      <a
        href={href}
        className="no-underline opacity-70 hover:opacity-100 transition"
        style={{ color: "inherit" }}
      >
        {label}
      </a>
    </li>
  );
}
