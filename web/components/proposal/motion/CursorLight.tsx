"use client";

import { motion, useMotionValue, useSpring } from "motion/react";
import { useEffect, useState } from "react";

/**
 * マウスに追従する小円のカスタムカーソル。
 * `(pointer: fine)` 端末のみ有効。システムカーソルは残したまま上に overlay。
 * reduce-motion は <MotionRoot> の reducedMotion="user" で吸収される。
 */
export function CursorLight() {
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const sx = useSpring(x, { stiffness: 400, damping: 35, mass: 0.4 });
  const sy = useSpring(y, { stiffness: 400, damping: 35, mass: 0.4 });
  const [active, setActive] = useState(false);
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fine = window.matchMedia("(pointer: fine)").matches;
    if (!fine) return;
    setEnabled(true);

    function onMove(e: MouseEvent) {
      x.set(e.clientX);
      y.set(e.clientY);
      const t = document.elementFromPoint(e.clientX, e.clientY);
      if (!t) return;
      const hit = t.closest(
        'a, button, [role="button"], [data-cursor="hover"], summary, input, select, textarea',
      );
      setActive(!!hit);
    }
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [x, y]);

  if (!enabled) return null;

  return (
    <motion.div
      aria-hidden
      style={{
        x: sx,
        y: sy,
        position: "fixed",
        top: 0,
        left: 0,
        width: 14,
        height: 14,
        borderRadius: "50%",
        background: "#ffffff",
        mixBlendMode: "difference",
        pointerEvents: "none",
        translateX: "-50%",
        translateY: "-50%",
        zIndex: 9999,
        scale: active ? 2.8 : 1,
        transition: "scale 260ms cubic-bezier(0.22, 1, 0.36, 1)",
      }}
    />
  );
}
