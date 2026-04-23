import { Theme } from "./Theme";
import { Nav, NavItem } from "./Nav";
import { Hero } from "./Hero";
import { Section } from "./Section";
import { Grid } from "./Grid";
import { Card } from "./Card";
import { Stats, Stat } from "./Stats";
import { FAQ, FAQItem } from "./FAQ";
import { CTA } from "./CTA";
import { AudienceCTA } from "./AudienceCTA";
import { Quote } from "./Quote";
import { Image } from "./Image";
import { Prose } from "./Prose";
import { Footer, FooterLine, FooterLink } from "./Footer";

// motion primitives
import { Reveal } from "./motion/Reveal";
import { Stagger } from "./motion/Stagger";
import { Parallax } from "./motion/Parallax";
import { Magnetic } from "./motion/Magnetic";
import { Tilt } from "./motion/Tilt";
import { Ticker } from "./motion/Ticker";
import { TextReveal } from "./motion/TextReveal";
import { Marquee } from "./motion/Marquee";

/**
 * MDX の <Tag /> で使えるコンポーネントを束ねたマップ。
 * next-mdx-remote の components prop にそのまま渡す。
 */
export const proposalComponents = {
  // structure
  Theme,
  Nav,
  NavItem,
  Hero,
  Section,
  Grid,
  Card,
  Stats,
  Stat,
  FAQ,
  FAQItem,
  CTA,
  AudienceCTA,
  Quote,
  Image,
  Prose,
  Footer,
  FooterLine,
  FooterLink,
  // motion
  Reveal,
  Stagger,
  Parallax,
  Magnetic,
  Tilt,
  Ticker,
  TextReveal,
  Marquee,
};
