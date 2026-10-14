// next.config.mjs derleme anında doldurur (package.json sürümü + kaynak commit).
export const APP_VERSION = process.env.APP_VERSION || "0.0.0";
export const APP_COMMIT = process.env.APP_COMMIT || "";

/** SemVer derleme üst verisiyle tam sürüm: 0.2.0 veya 0.2.0+abc1234. */
export function fullVersion(version: string = APP_VERSION, commit: string = APP_COMMIT) {
  return commit ? `${version}+${commit}` : version;
}

/** Arayüzde gösterilen kısa etiket: v0.2.0 */
export function versionLabel(version: string = APP_VERSION) {
  return `v${version}`;
}

/** Web ve API farklı sürümdeyse (ör. yarım kalmış dağıtım) uyarı metni döner. */
export function versionSkew(webVersion: string, apiVersion: string | null | undefined) {
  if (!apiVersion) return null;
  const base = (value: string) => value.split("+")[0];
  return base(webVersion) === base(apiVersion) ? null : `Web v${base(webVersion)} · API v${base(apiVersion)}`;
}
