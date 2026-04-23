import { ReactNode } from "react";

type NavProps = {
  brand: string;
  /** ロゴ画像 URL（あれば brand 文字と並べて表示） */
  logo?: string;
  logoAlt?: string;
  children?: ReactNode;
};

/**
 * 上部のナビ。brand（団体名）+ 任意の logo 画像 + children に <NavItem>。
 */
export function Nav({ brand, logo, logoAlt, children }: NavProps) {
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
        className="flex items-center gap-3 font-bold text-base sm:text-lg no-underline"
        style={{ color: "var(--color-primary)" }}
      >
        {logo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={logo}
            alt={logoAlt || brand}
            className="w-8 h-8 sm:w-9 sm:h-9 rounded-full object-cover"
          />
        )}
        <span>{brand}</span>
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
        className={[
          "group no-underline opacity-80 hover:opacity-100 transition-opacity",
          "relative inline-block py-1",
        ].join(" ")}
        style={{ color: "inherit" }}
      >
        {label}
        <span
          aria-hidden
          className="absolute left-0 bottom-0 h-[1.5px] w-full origin-left scale-x-0 transition-transform duration-300 ease-out group-hover:scale-x-100"
          style={{ background: "currentColor" }}
        />
      </a>
    </li>
  );
}
