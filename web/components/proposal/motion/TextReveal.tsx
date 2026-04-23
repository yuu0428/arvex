"use client";

import { motion, useInView, useReducedMotion } from "motion/react";
import { useRef } from "react";

type TextRevealProps = {
  children: string;
  /** 単語単位か文字単位か。デフォルトは単語 */
  by?: "word" | "char";
  delay?: number;
  stagger?: number;
};

/** 文字列を単語・文字単位で分割して、下から上へ順番に表出させる。h1/h2 のエントリに。 */
export function TextReveal({
  children,
  by = "word",
  delay = 0,
  stagger = 0.05,
}: TextRevealProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-30px" });
  const reduce = useReducedMotion();

  const segments =
    by === "char"
      ? Array.from(children)
      : children.split(/(\s+)/);

  if (reduce) {
    return <span ref={ref}>{children}</span>;
  }

  return (
    <span ref={ref} style={{ display: "inline-block" }}>
      {segments.map((seg, i) =>
        seg.trim() === "" ? (
          <span key={i}>{seg}</span>
        ) : (
          <motion.span
            key={i}
            style={{ display: "inline-block", willChange: "transform, opacity" }}
            initial={{ opacity: 0, y: "90%" }}
            animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: "90%" }}
            transition={{
              duration: 0.7,
              delay: delay + i * stagger,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            {seg}
          </motion.span>
        ),
      )}
    </span>
  );
}
