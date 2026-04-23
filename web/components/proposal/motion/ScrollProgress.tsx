"use client";

import { motion, useScroll, useSpring } from "motion/react";

/**
 * ページ上端の細い scroll progress bar。
 * reduce-motion は <MotionRoot> 側で処理されるのでここでは何もしない。
 */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 200, damping: 30 });

  return (
    <motion.div
      aria-hidden
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: 2,
        transformOrigin: "0%",
        scaleX,
        background: "var(--color-tertiary, var(--color-primary, #0a0a0a))",
        zIndex: 60,
      }}
    />
  );
}
