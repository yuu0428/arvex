"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { useRef, ReactNode } from "react";

type ParallaxProps = {
  children: ReactNode;
  speed?: number;
};

/** 対象要素のスクロール進捗に bind した translate。subtle に使う。 */
export function Parallax({ children, speed = 0.3 }: ParallaxProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const clamp = Math.max(-1, Math.min(1, speed));
  const y = useTransform(scrollYProgress, [0, 1], [`${-clamp * 80}px`, `${clamp * 80}px`]);

  return (
    <motion.div ref={ref} style={{ y }}>
      {children}
    </motion.div>
  );
}
