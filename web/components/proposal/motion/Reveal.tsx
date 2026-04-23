"use client";

import { motion, useInView, useReducedMotion } from "motion/react";
import { useRef, ReactNode } from "react";

type RevealProps = {
  children: ReactNode;
  variant?: "fade" | "up" | "down" | "left" | "right" | "scale";
  delay?: number;
  duration?: number;
  distance?: number;
};

/** viewport に入ったタイミングで1度だけ表出するラッパー */
export function Reveal({
  children,
  variant = "up",
  delay = 0,
  duration = 1.0,
  distance = 64,
}: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -15% 0px" });
  const reduce = useReducedMotion();

  const initial: Record<string, number | string> = reduce
    ? { opacity: 0 }
    : {
        fade: { opacity: 0 },
        up: { opacity: 0, y: distance },
        down: { opacity: 0, y: -distance },
        left: { opacity: 0, x: -distance },
        right: { opacity: 0, x: distance },
        scale: { opacity: 0, scale: 0.96 },
      }[variant];

  return (
    <motion.div
      ref={ref}
      initial={initial}
      animate={inView ? { opacity: 1, x: 0, y: 0, scale: 1 } : initial}
      transition={{ duration: reduce ? 0 : duration, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
