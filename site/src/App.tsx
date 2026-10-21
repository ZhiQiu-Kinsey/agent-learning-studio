import { useTranslation } from "react-i18next";
import { Closing } from "./components/Closing";
import { CurriculumMap } from "./components/CurriculumMap";
import { Features } from "./components/Features";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { Honesty } from "./components/Honesty";
import { Loop } from "./components/Loop";
import { QuickStart } from "./components/QuickStart";
import { Replays } from "./components/Replays";
import { Stats } from "./components/Stats";

export default function App() {
  const { t } = useTranslation("site", { keyPrefix: "footer" });
  return (
    <>
      <Header />
      <main id="main">
        <Hero />
        <Stats />
        <Loop />
        <Features />
        <Replays />
        <CurriculumMap />
        <QuickStart />
        <Honesty />
        <Closing />
      </main>
      <footer className="site-footer">
        <p>{t("license")}</p>
        <p>{t("static")}</p>
      </footer>
    </>
  );
}
