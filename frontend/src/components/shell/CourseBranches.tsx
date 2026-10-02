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
 * of the trunk; the hovered lesson's branch brightens. Purely decorative.
 *
 * Every coordinate is measured, never assumed: the root font size follows the
 * viewport (base.css), so rem-based rows and px constants would drift apart.
 * - trunk x: centre of the domain icon (`[data-branch-root]` in the section);
 * - node y: centre of the first text line of each `[data-branch-node]`;
 * - branch y: centre of the first text line of the row's `[data-branch-anchor]`
 *   (falls back to the row), so wrapped titles keep the branch on line one;
 * - branch end x: just before the row's left edge.
 */
const RADIUS = 7;
/** Gap between a branch tip and its row. */
const TIP_GAP = 1;

interface Row {
  id: string;
  y: number;
  end: number;
  planned: boolean;
}
interface Geometry {
  trunk: number;
  rows: Row[];
  nodes: number[];
  height: number;
}

const round = (value: number) => Math.round(value * 4) / 4;

/**
 * Vertical centre of the first line of text in `el`, relative to `top`. Rows
 * only ever move sideways while entering, so client boxes are safe for y.
 */
function firstLineCentre(el: HTMLElement, top: number) {
  // The first text fragment's own box: CJK glyphs come from a fallback font
  // whose box sits higher than the Latin line box, so prefer the real glyphs.
  const range = document.createRange();
  range.selectNodeContents(el);
  const glyphs = range.getClientRects()[0];
  range.detach();
  if (glyphs && glyphs.height > 0) return glyphs.top - top + glyphs.height / 2;
  const style = getComputedStyle(el);
  const line = parseFloat(style.lineHeight);
  const padding = parseFloat(style.paddingTop) || 0;
  const box = el.getBoundingClientRect();
  const height = Number.isFinite(line)
    ? Math.min(line, box.height)
    : box.height;
  return box.top - top + padding + height / 2;
}

/**
 * Left edge of a row, relative to `left`: its (untransformed) container plus
 * its margin, so the sideways entrance animation never skews the tips.
 */
function rowStart(el: HTMLElement, left: number) {
  const container = el.parentElement ?? el;
  return (
    container.getBoundingClientRect().left -
    left +
    (parseFloat(getComputedStyle(el).marginLeft) || 0)
  );
}

function sameGeometry(a: Geometry | null, b: Geometry) {
  if (!a || a.height !== b.height || a.trunk !== b.trunk) return false;
  if (a.rows.length !== b.rows.length || a.nodes.join() !== b.nodes.join())
    return false;
  return a.rows.every(
    (row, i) =>
      row.id === b.rows[i].id &&
      row.y === b.rows[i].y &&
      row.end === b.rows[i].end &&
      row.planned === b.rows[i].planned,
  );
}

function measure(host: HTMLElement): Geometry | null {
  // Collapsed (hidden or zero-width) content keeps the last geometry.
  if (!host.offsetParent || host.offsetWidth === 0) return null;
  const icon =
    host.parentElement?.querySelector<HTMLElement>("[data-branch-root]");
  const hostBox = host.getBoundingClientRect();
  const iconBox = icon?.getBoundingClientRect();
  const trunk = round(
    iconBox ? iconBox.left + iconBox.width / 2 - hostBox.left : 17,
  );
  const rows = Array.from(
    host.querySelectorAll<HTMLElement>("[data-branch-id]"),
  ).map((el) => ({
    id: el.dataset.branchId || "",
    y: round(
      firstLineCentre(
        el.querySelector<HTMLElement>("[data-branch-anchor]") ?? el,
        hostBox.top,
      ),
    ),
    end: round(Math.max(trunk + 2, rowStart(el, hostBox.left) - TIP_GAP)),
    planned: el.hasAttribute("data-branch-planned"),
  }));
  const nodes = Array.from(
    host.querySelectorAll<HTMLElement>("[data-branch-node]"),
  ).map((el) => round(firstLineCentre(el, hostBox.top)));
  return { trunk, rows, nodes, height: Math.round(host.scrollHeight) };
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
    let cancelled = false;
    const update = () => {
      if (cancelled) return;
      const next = measure(host);
      if (next)
        setGeometry((previous) =>
          sameGeometry(previous, next) ? previous : next,
        );
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(host);
    host
      .querySelectorAll("[data-branch-id], [data-branch-node]")
      .forEach((el) => observer.observe(el));
    // Web fonts change line boxes without always resizing the rows' width.
    void document.fonts?.ready.then(update);
    return () => {
      cancelled = true;
      observer.disconnect();
    };
  }, [open, signature]);

  const rows = geometry?.rows ?? [];
  const trunk = geometry?.trunk ?? 0;
  const last = rows.length ? rows[rows.length - 1].y : 0;
  const width = Math.max(trunk, ...rows.map((row) => row.end)) + 2;
  // Corner radius shrinks when a branch is shorter than a full quarter turn.
  const radius = (row: Row) =>
    Math.max(2, Math.min(RADIUS, row.end - trunk - 1));
  const arc = (row: Row) => {
    const r = radius(row);
    return `A ${r} ${r} 0 0 0 ${trunk + r} ${row.y} H ${row.end}`;
  };
  const branch = (row: Row) => `M ${trunk} ${row.y - radius(row)} ${arc(row)}`;
  const reach = (row: Row) =>
    `M ${trunk} 0 V ${row.y - radius(row)} ${arc(row)}`;
  const tail = (row: Row) =>
    (Math.PI * radius(row)) / 2 + (row.end - trunk - radius(row));
  return (
    <svg
      ref={ref}
      className="nav-branches"
      width={width}
      height={geometry?.height ?? 0}
      aria-hidden="true"
      focusable="false"
    >
      {rows.length > 0 && (
        <>
          <path
            className="nav-branch-trunk"
            d={`M ${trunk} 0 V ${last - radius(rows[rows.length - 1])}`}
            style={{ "--len": Math.max(1, last - RADIUS) } as CSSProperties}
          />
          {geometry?.nodes.map((y) => (
            <circle
              key={`node-${y}`}
              className="nav-branch-node"
              cx={trunk}
              cy={y}
              r={2.75}
            />
          ))}
          {rows.map((row, i) => (
            <path
              key={row.id}
              className={`nav-branch${row.planned ? " is-planned" : ""}${
                hoveredId === row.id && row.id !== activeId ? " is-hover" : ""
              }`}
              d={branch(row)}
              style={{ "--len": tail(row) + 1, "--i": i } as CSSProperties}
            />
          ))}
          {rows.map((row) => {
            const length = row.y - radius(row) + tail(row);
            const active = row.id === activeId;
            return (
              <path
                key={`reach-${row.id}`}
                className={`nav-branch-reach${active ? " is-active" : ""}`}
                d={reach(row)}
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
