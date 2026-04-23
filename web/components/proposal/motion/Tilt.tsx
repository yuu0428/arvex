"use client";

import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import { useRef, ReactNode } from "react";

type TiltProps = {
  children: ReactNode;
  max?: number;
};

/** Card 等に 3D tilt を与える。 */
export function Tilt({ children, max = 8 }: TiltProps) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0.5);
  const y = useMotionValue(0.5);
  const sx = useSpring(x, { stiffness: 180, damping: 20 });
  const sy = useSpring(y, { stiffness: 180, damping: 20 });
  const rotateX = useTransform(sy, [0, 1], [max, -max]);
  const rotateY = useTransform(sx, [0, 1], [-max, max]);

  function onMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    x.set((e.clientX - r.left) / r.width);
    y.set((e.clientY - r.top) / r.height);
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={() => { x.set(0.5); y.set(0.5); }}
      style={{ rotateX, rotateY, transformPerspective: 1200 }}
    >
      {children}
    </motion.div>
  );
}
