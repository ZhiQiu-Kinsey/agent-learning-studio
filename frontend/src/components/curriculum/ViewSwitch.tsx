import { useTranslation } from "react-i18next";
import { LayoutGrid, List, Route, type LucideIcon } from "lucide-react";
import { TabsList, TabsTrigger } from "../ui/tabs";
import GooeyNav from "../react-bits/GooeyNav";
import type { MapView } from "./useMapView";

const viewTabs: { id: MapView; Icon: LucideIcon }[] = [
  { id: "domains", Icon: LayoutGrid },
  { id: "roadmap", Icon: Route },
  { id: "list", Icon: List },
];

/** Tab list for the three map views; must sit inside the map's `<Tabs>`. */
export function ViewSwitch({ view }: { view: MapView }) {
  const { t } = useTranslation("curriculum");
  return (
    <TabsList
      variant="line"
      className="curriculum-view-switch"
      aria-label={t("views.label")}
      data-testid="curriculum-view-switch"
    >
      {/* Active indicator: gooey blob that bursts on a real view switch. */}
      <GooeyNav activeKey={view} className="curriculum-view-goo" />
      {viewTabs.map(({ id, Icon }) => (
        <TabsTrigger key={id} value={id} data-testid={`curriculum-view-${id}`}>
          <Icon aria-hidden="true" />
          <span>{t(`views.${id}`)}</span>
        </TabsTrigger>
      ))}
    </TabsList>
  );
}
