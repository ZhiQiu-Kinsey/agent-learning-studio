import { Component, Suspense, type ReactNode } from "react";
import { lessonExtensions } from "./registry";
import type { LessonExtensionSlots } from "./types";

const labels = { guide: "课程导读", lab: "实验工作台", inspector: "执行观察" };

function Fallback({
  label,
  reason,
  children,
}: {
  label: string;
  reason: string;
  children: ReactNode;
}) {
  return (
    <>
      <div className="workspace-error" role="alert">
        {label}的专属视图{reason}，已显示通用界面。课程内容和运行记录仍可使用。
      </div>
      {children}
    </>
  );
}

class ExtensionBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

/** Unregistered keys and a failed extension never remove the default workspace. */
export function LessonExtension<Slot extends keyof LessonExtensionSlots>(
  props: { slot: Slot; extensionKey?: string } & LessonExtensionSlots[Slot],
) {
  const { slot, extensionKey } = props;
  if (!extensionKey) return props.children;
  const registry = lessonExtensions[slot];
  const Extension = Object.hasOwn(registry, extensionKey)
    ? registry[extensionKey]
    : undefined;
  if (!Extension)
    return (
      <Fallback label={labels[slot]} reason="暂不可用">
        {props.children}
      </Fallback>
    );
  return (
    <ExtensionBoundary
      key={`${props.studio.lessonId}:${slot}:${extensionKey}`}
      fallback={
        <Fallback label={labels[slot]} reason="加载失败">
          {props.children}
        </Fallback>
      }
    >
      <Suspense
        fallback={
          <>
            <p role="status">正在准备本课专属视图…</p>
            {props.children}
          </>
        }
      >
        <Extension key={extensionKey} {...props} />
      </Suspense>
    </ExtensionBoundary>
  );
}
