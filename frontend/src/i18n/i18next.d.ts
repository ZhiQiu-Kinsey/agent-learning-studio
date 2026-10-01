import "i18next";
import type { sourceResources } from "./resources";

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "common";
    resources: typeof sourceResources;
  }
}
