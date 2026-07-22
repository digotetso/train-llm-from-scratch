import { homedir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";

export interface ExporterPaths {
  root: string;
  tmp: string;
  incoming: string;
  quarantine: string;
  assets: string;
  logs: string;
}

export function exporterRoot(): string {
  return join(homedir(), "Library", "Application Support", "Video001FigmaAEExporter");
}

export function exporterPaths(root: string = exporterRoot()): ExporterPaths {
  if (!isAbsolute(root)) throw new TypeError("Exporter root must be an absolute path");
  const resolvedRoot = resolve(root);
  return {
    root: resolvedRoot,
    tmp: join(resolvedRoot, "tmp"),
    incoming: join(resolvedRoot, "incoming"),
    quarantine: join(resolvedRoot, "quarantine"),
    assets: join(resolvedRoot, "assets"),
    logs: join(resolvedRoot, "logs")
  };
}
