import { homedir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";

const PROJECT_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?$/;

function validatePathProjectId(value: string): string {
  if (!PROJECT_ID_PATTERN.test(value)) throw new TypeError("Invalid project profile at $.project.id: unsafe project ID");
  return value;
}

export interface GenericExporterPaths {
  root: string;
  auth: string;
  profiles: string;
  projects: string;
  tmp: string;
}

export interface ProjectPaths {
  root: string;
  incoming: string;
  quarantine: string;
  assets: string;
  logs: string;
  tmp: string;
}

/** @deprecated The pre-profile queue's temporary compatibility layout. */
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

export function exporterPaths(root: string = exporterRoot()): GenericExporterPaths {
  if (!isAbsolute(root)) throw new TypeError("Exporter root must be an absolute path");
  const resolvedRoot = resolve(root);
  return {
    root: resolvedRoot,
    auth: join(resolvedRoot, "auth"),
    profiles: join(resolvedRoot, "profiles"),
    projects: join(resolvedRoot, "projects"),
    tmp: join(resolvedRoot, "tmp")
  };
}

/** @deprecated QueueStore compatibility until queue storage becomes project-scoped. */
export function legacyExporterPaths(root: string = exporterRoot()): ExporterPaths {
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

export function projectPaths(paths: GenericExporterPaths, projectId: string): ProjectPaths {
  const id = validatePathProjectId(projectId);
  const root = join(paths.projects, id);
  return {
    root,
    incoming: join(root, "incoming"),
    quarantine: join(root, "quarantine"),
    assets: join(root, "assets"),
    logs: join(root, "logs"),
    tmp: join(root, "tmp")
  };
}
