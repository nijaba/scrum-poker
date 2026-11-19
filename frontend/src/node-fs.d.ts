/**
 * The one Node function vite.config.ts uses, to read the version from pyproject.toml. Declared
 * here rather than adding @types/node for it; remove this file if @types/node is ever added.
 */
declare module "node:fs" {
  export function readFileSync(path: URL | string, encoding: "utf8"): string;
}
