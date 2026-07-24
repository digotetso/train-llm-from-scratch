import {
  ProfileRegistryCore,
  realProfileRegistryFilesystem,
  type ProfileRegistryEvent
} from "./profile-registry-internal.ts";
import type { GenericExporterPaths } from "./paths.ts";
import type { InstalledProfile, ProfileProjection, ProfileReference, ProfileSummary } from "../shared/project-profile.ts";

export type { ProfileRegistryEvent } from "./profile-registry-internal.ts";

export class ProfileRegistry {
  private readonly core: ProfileRegistryCore;

  constructor(paths: GenericExporterPaths, options: { now?: () => number; record?: (event: ProfileRegistryEvent) => void } = {}) {
    this.core = new ProfileRegistryCore(paths, realProfileRegistryFilesystem, options);
  }

  installFile(sourcePath: string): Promise<InstalledProfile> { return this.core.installFile(sourcePath); }
  installValue(value: unknown): Promise<InstalledProfile> { return this.core.installValue(value); }
  list(): Promise<ProfileSummary[]> { return this.core.list(); }
  resolve(reference: ProfileReference): Promise<InstalledProfile> { return this.core.resolve(reference); }
  projection(reference: ProfileReference): Promise<ProfileProjection> { return this.core.projection(reference); }
}
