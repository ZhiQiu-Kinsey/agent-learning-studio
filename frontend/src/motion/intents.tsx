import {
  lazy,
  Suspense,
  type ComponentType,
  type LazyExoticComponent,
} from "react";
import type { SplitTextProps } from "../components/react-bits/SplitText";
import { useMotion } from "./context";
import type { MotionLevel } from "./level";
import type { MotionCost } from "./useMotionBudget";

/**
 * Semantic effect registry: content and pages ask for an intent, never for a
 * specific library component. Each entry declares its cost, the levels it may
 * run at, a lazy loader and a static fallback that carries the same meaning.
 * Viewport/WebGL budgets are enforced inside the effect via useMotionBudget.
 */
interface IntentEntry<P> {
  cost: MotionCost;
  levels: readonly MotionLevel[];
  load: () => Promise<{ default: ComponentType<P> }>;
  Fallback: ComponentType<P>;
}

interface IntentPropsMap {
  "heading.split": SplitTextProps;
}
export type IntentName = keyof IntentPropsMap;
type IntentProps<N extends IntentName> = IntentPropsMap[N];

export const intents: { [N in IntentName]: IntentEntry<IntentProps<N>> } = {
  "heading.split": {
    cost: "css",
    levels: ["full"],
    load: () => import("../components/react-bits/SplitText"),
    Fallback: ({ text, tag: Tag = "p", className }) => (
      <Tag className={className}>{text}</Tag>
    ),
  },
};

// Internal storage erases props; MotionIntent restores them from the registry key.
type AnyComponent = ComponentType<any>;
const loaded = new Map<IntentName, LazyExoticComponent<AnyComponent>>();
function lazyIntent(name: IntentName) {
  let component = loaded.get(name);
  if (!component) {
    component = lazy(intents[name].load as () => Promise<{ default: AnyComponent }>);
    loaded.set(name, component);
  }
  return component;
}

export function MotionIntent<N extends IntentName>({
  name,
  ...props
}: { name: N } & IntentProps<N>) {
  const { level, webgl } = useMotion();
  const entry = intents[name] as IntentEntry<unknown>;
  const Fallback = entry.Fallback as AnyComponent;
  if (!entry.levels.includes(level) || (entry.cost === "webgl" && !webgl))
    return <Fallback {...props} />;
  const Effect = lazyIntent(name);
  return (
    <Suspense fallback={<Fallback {...props} />}>
      <Effect {...props} />
    </Suspense>
  );
}
