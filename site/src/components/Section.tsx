import type { ReactNode } from "react";
import FadeContent from "@studio/components/react-bits/FadeContent";

/** A page section with the shared eyebrow / title / lead header, revealed on scroll. */
export function Section({
  id,
  eyebrow,
  title,
  lead,
  wide = false,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  lead?: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <section
      className={`site-section${wide ? " is-wide" : ""}`}
      id={id}
      aria-labelledby={`${id}-title`}
    >
      <FadeContent className="site-section-head">
        <p className="site-kicker">{eyebrow}</p>
        <h2 id={`${id}-title`}>{title}</h2>
        {lead && <p className="site-section-lead">{lead}</p>}
      </FadeContent>
      {children}
    </section>
  );
}
