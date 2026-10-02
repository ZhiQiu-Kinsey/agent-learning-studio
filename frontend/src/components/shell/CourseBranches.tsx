import {
  memo,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";

/**
 * BranchedMenu-style lines for one open domain (React Bits BranchedMenu, adapted
 * to measured rows): a trunk drops from the domain icon and a curved branch
 * reaches every lesson. The current lesson gets a tinted line drawn from the top
 * of the trunk; the hovered lesson's branch brightens. Rows can wrap, so the
 * geometry is measured from `[data-branch-id]` / `[data-branch-node]` elements
 * in the parent instead of assuming a fixed row height. Purely decorative.
 *
 * Horizontal positions are in px and must match `--branch-indent` in
 * shell-experience.css (trunk under the domain icon, rows start after END).
 */
const TRUNK = 17;
const END = 30;
const R = 7;

interface Row {
  id: string;
  y: number;
  planned: boolean;
}
interface Geometry {
  rows: Row[];
  nodes: number[];
  height: number;
}

const arc = (y: number) => `A ${R} ${R} 0 0 0 ${TRUNK + R} ${y} H ${END}`;
const branch = (y: number) => `M ${TRUNK} ${y - R} ${arc(y)}`;
const reach = (y: number) => `M ${TRUNK} 0 V ${y - R} ${arc(y)}`;
const tail = (Math.PI * R) / 2 + (END - TRUNK - R);
const reachLength = (y: number) => y - R + tail;

function sameGeometry(a: Geometry | null, b: Geometry) {
  if (!a || a.height !== b.height || a.rows.length !== b.rows.length)
    return false;
  if (a.nodes.join() !== b.nodes.join()) return false;
  return a.rows.every(
    (row, i) =>
      row.id === b.rows[i].id &&
      row.y === b.rows[i].y &&
      row.planned === b.rows[i].planned,
  );
}

export const CourseBranches = memo(function CourseBranches({
  open,
  activeId,
  hoveredId,
  signature,
}: {
  open: boolean;
  /** Changes when rows change (ids, availability), so geometry is re-read. */
  signature: string;
  activeId?: string;
  hoveredId?: string | null;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [geometry, setGeometry] = useState<Geometry | null>(null);

  useLayoutEffect(() => {
    const host = ref.current?.parentElement;
    if (!host || !open) return;
    const measure = () => {
      const box = host.getBoundingClientRect();
      // Collapsed (hidden or zero-height) content keeps the last geometry.
      if (!host.offsetParent || box.width === 0) return;
      const centre = (el: Element) => {
        const rect = el.getBoundingClientRect();
        return Math.round(rect.top - box.top + rect.height / 2);
      };
      const next: Geometry = {
        rows: Array.from(
          host.querySelectorAll<HTMLElement>("[data-branch-id]"),
        ).map((el) => ({
          id: el.dataset.branchId || "",
          y: centre(el),
          planned: el.hasAttribute("data-branch-planned"),
        })),
        nodes: Array.from(host.querySelectorAll("[data-branch-node]")).map(
          centre,
        ),
        height: Math.round(host.scrollHeight),
      };
      setGeometry((previous) =>
        sameGeometry(previous, next) ? previous : next,
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(host);
    host
      .querySelectorAll("[data-branch-id]")
      .forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [open, signature]);

  const rows = geometry?.rows ?? [];
  const last = rows.length ? rows[rows.length - 1].y : 0;
  return (
    <svg
      ref={ref}
      className="nav-branches"
      width={END + 2}
      height={geometry?.height ?? 0}
      aria-hidden="true"
      focusable="false"
    >
      {rows.length > 0 && (
        <>
          <path
            className="nav-branch-trunk"
            d={`M ${TRUNK} 0 V ${last - R}`}
            style={{ "--len": Math.max(1, last - R) } as CSSProperties}
          />
          {geometry?.nodes.map((y) => (
            <circle
              key={`node-${y}`}
              className="nav-branch-node"
              cx={TRUNK}
              cy={y}
              r={2.6}
            />
          ))}
          {rows.map((row, i) => (
            <path
              key={row.id}
              className={`nav-branch${row.planned ? " is-planned" : ""}${
                hoveredId === row.id && row.id !== activeId ? " is-hover" : ""
              }`}
              d={branch(row.y)}
              style={{ "--len": tail + 1, "--i": i } as CSSProperties}
            />
          ))}
          {rows.map((row) => {
            const length = reachLength(row.y);
            const active = row.id === activeId;
            return (
              <path
                key={`reach-${row.id}`}
                className={`nav-branch-reach${active ? " is-active" : ""}`}
                d={reach(row.y)}
                style={{
                  strokeDasharray: length,
                  strokeDashoffset: active ? 0 : length,
                }}
              />
            );
          })}
        </>
      )}
    </svg>
  );
});
