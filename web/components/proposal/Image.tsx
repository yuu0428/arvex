type ImageRole = "hero" | "card" | "thumb" | "logo" | "banner" | "full";

type RoleDefaults = {
  aspect: string;
  maxWidth: number | null; // null = no cap (full-bleed)
  fit: "cover" | "contain";
};

const ROLE_DEFAULTS: Record<ImageRole, RoleDefaults> = {
  hero: { aspect: "16/9", maxWidth: 720, fit: "cover" },
  card: { aspect: "4/3", maxWidth: 480, fit: "cover" },
  thumb: { aspect: "1/1", maxWidth: 240, fit: "cover" },
  logo: { aspect: "1/1", maxWidth: 120, fit: "contain" },
  banner: { aspect: "21/9", maxWidth: 1280, fit: "cover" },
  full: { aspect: "16/9", maxWidth: null, fit: "cover" },
};

type ImageProps = {
  src: string;
  alt: string;
  caption?: string;
  role?: ImageRole;
  // role の defaults を上書きするための任意 props
  aspect?: string; // "16/9", "4/3", "320/200" 等
  maxWidth?: number; // px
  fit?: "cover" | "contain";
  rounded?: boolean;
  className?: string;
};

/**
 * MDX 内でスタイル一貫・PC でも崩れない画像ラッパー。
 *
 * 使い方:
 *   <Image src="..." alt="..." role="hero" />          // 16:9, max 720px, cover
 *   <Image src="..." alt="..." role="card" />          // 4:3, max 480px, cover
 *   <Image src="..." alt="..." role="thumb" />         // 1:1, max 240px, cover
 *   <Image src="..." alt="..." role="logo" />          // 1:1, max 120px, contain
 *   <Image src="..." alt="..." role="banner" />        // 21:9, max 1280px, cover
 *   <Image src="..." alt="..." role="full" />          // 16:9, full-bleed, cover
 *
 * fine-tune したい時:
 *   <Image src="..." alt="..." role="card" aspect="3/2" maxWidth={600} />
 *
 * caption / rounded / className は任意。raw <img> を書く時は SYSTEM_PROMPT の
 * 4 属性必須ルール（aspectRatio / width / maxWidth / objectFit）を厳守。
 */
export function Image({
  src,
  alt,
  caption,
  role = "card",
  aspect,
  maxWidth,
  fit,
  rounded = true,
  className = "",
}: ImageProps) {
  const defaults = ROLE_DEFAULTS[role];
  const aspectRatio = aspect ?? defaults.aspect;
  const cap = maxWidth ?? defaults.maxWidth;
  const objectFit = fit ?? defaults.fit;

  return (
    <figure
      className={`my-8 mx-auto ${className}`}
      style={cap ? { maxWidth: `${cap}px` } : undefined}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        className={`block w-full ${rounded ? "rounded-xl" : ""}`}
        style={{
          aspectRatio,
          objectFit,
        }}
      />
      {caption && (
        <figcaption className="text-sm opacity-70 mt-3 text-center">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
