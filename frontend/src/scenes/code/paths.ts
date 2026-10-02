/** Small path / language helpers shared by the code scene parts. */
export const prismLanguage = (language: string) =>
  language === "py" ? "python" : language;
export const basename = (path: string) => path.slice(path.lastIndexOf("/") + 1);
export const dirname = (path: string) =>
  path.slice(0, path.lastIndexOf("/") + 1);
