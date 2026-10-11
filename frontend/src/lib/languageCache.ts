/**
 * One shared request per content language. Content endpoints answer in the
 * UI language (`?lang=`), so a cache keyed by path alone would keep serving
 * the old language after a switch. A failed request is forgotten so the next
 * caller retries.
 */
export function createLanguageCache<T>(fetcher: (language: string) => Promise<T>) {
  const values = new Map<string, T>();
  const pending = new Map<string, Promise<T>>();
  return {
    /** The loaded value for `language`, if any. */
    peek(language: string): T | undefined {
      return values.get(language);
    },
    load(language: string): Promise<T> {
      const hit = values.get(language);
      if (hit !== undefined) return Promise.resolve(hit);
      let request = pending.get(language);
      if (!request) {
        request = fetcher(language).then(
          (value) => {
            values.set(language, value);
            pending.delete(language);
            return value;
          },
          (error: unknown) => {
            pending.delete(language);
            throw error;
          },
        );
        pending.set(language, request);
      }
      return request;
    },
  };
}
