type ImageProps = {
  src: string;
  alt: string;
  caption?: string;
  aspect?: "16/9" | "4/3" | "3/2" | "1/1" | "9/16";
  rounded?: boolean;
};

/**
 * MDX 内でスタイル一貫の画像を置くためのラッパー。
 */
export function Image({ src, alt, caption, aspect = "16/9", rounded = true }: ImageProps) {
  return (
    <figure className="my-8">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        className={`w-full object-cover ${rounded ? "rounded-xl" : ""}`}
        style={{ aspectRatio: aspect }}
      />
      {caption && <figcaption className="text-sm opacity-70 mt-3">{caption}</figcaption>}
    </figure>
  );
}
