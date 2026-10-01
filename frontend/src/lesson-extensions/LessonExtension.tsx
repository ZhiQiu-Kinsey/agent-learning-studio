import { Component, Suspense, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { lessonExtensions } from "./registry";
import type { LessonExtensionSlots } from "./types";

function Fallback({
  slot,
  reason,
  children,
}: {
  slot: keyof LessonExtensionSlots;
  reason: "unavailable" | "failed";
  children: ReactNode;
}) {
  const { t } = useTranslation("lab");
  return (
    <>
      <div className="workspace-error" role="alert">
        {t(`extension.${reason}`, { slot: t(`extension.slot.${slot}`) })}
      </div>
      {children}
    </>
  );
}

function ExtensionLoading() {
  const { t } = useTranslation("lab");
  return <p role="status">{t("extension.loading")}</p>;
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
      <Fallback slot={slot} reason="unavailable">
        {props.children}
      </Fallback>
    );
  return (
    <ExtensionBoundary
      key={`${props.studio.lessonId}:${slot}:${extensionKey}`}
      fallback={
        <Fallback slot={slot} reason="failed">
          {props.children}
        </Fallback>
      }
    >
      <Suspense
        fallback={
          <>
            <ExtensionLoading />
            {props.children}
          </>
        }
      >
        <Extension key={extensionKey} {...props} />
      </Suspense>
    </ExtensionBoundary>
  );
}
