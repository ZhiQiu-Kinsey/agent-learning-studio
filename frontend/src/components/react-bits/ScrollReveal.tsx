// React Bits ScrollReveal, adapted from https://reactbits.dev/r/ScrollReveal-TS-CSS.json.
// Copyright (c) 2026 David Haz. See LICENSE.md. Local GSAP cleanup and Chinese segmentation.
import { useEffect, useRef } from "react";
import { useReducedMotion } from "../../motion";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
gsap.registerPlugin(ScrollTrigger);

export default function ScrollReveal({
  children,
  className = "",
}: {
  children: string;
  className?: string;
}) {
  const ref = useRef<HTMLParagraphElement>(null);
  const reduced = useReducedMotion();
  useEffect(() => {
    const el = ref.current;
    if (!el || reduced) return;
    const context = gsap.context(() => {
      gsap.fromTo(
        el.querySelectorAll(".rb-reveal-word"),
        { opacity: 0.4, filter: "blur(1.5px)" },
        {
          opacity: 1,
          filter: "blur(0px)",
          stagger: 0.05,
          ease: "none",
          scrollTrigger: {
            trigger: el,
            start: "top 90%",
            end: "bottom 65%",
            scrub: true,
          },
        },
      );
    }, el);
    return () => context.revert();
  }, [children, reduced]);
  return (
    <p
      ref={ref}
      className={`rb-scroll-reveal ${className}`}
      aria-label={children}
    >
      {Array.from(children).map((char, index) => (
        <span key={index} aria-hidden="true" className="rb-reveal-word">
          {char}
        </span>
      ))}
    </p>
  );
}
