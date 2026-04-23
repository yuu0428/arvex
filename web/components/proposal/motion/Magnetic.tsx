"use client";

import { motion, useMotionValue, useSpring } from "motion/react";
import { useRef, ReactNode } from "react";

type MagneticProps = {
  children: ReactNode;
  strength?: number;
};

/** マウスに吸い寄せられる wrapper。CTA に使うと触れる感が出る。 */
export function Magnetic({ children, strength = 18 }: MagneticProps) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 150, damping: 15, mass: 0.3 });
  const sy = useSpring(y, { stiffness: 150, damping: 15, mass: 0.3 });

  function onMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    x.set(((e.clientX - cx) / (r.width / 2)) * strength);
    y.set(((e.clientY - cy) / (r.height / 2)) * strength);
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={() => { x.set(0); y.set(0); }}
      style={{ x: sx, y: sy, display: "inline-block" }}
    >
      {children}
    </motion.div>
  );
}
