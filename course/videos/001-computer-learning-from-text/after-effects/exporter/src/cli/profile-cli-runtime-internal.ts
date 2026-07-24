import { constants } from "node:fs";
import { link, lstat, open, unlink } from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import { randomUUID } from "node:crypto";

interface FileIdentity {
  device: number;
  inode: number;
}

export interface ProfileCliRuntimeFilesystem {
  open: typeof open;
  link: typeof link;
  lstat: typeof lstat;
  unlink: typeof unlink;
}

export const realProfileCliRuntimeFilesystem: Readonly<ProfileCliRuntimeFilesystem> = Object.freeze({ open, link, lstat, unlink });

function identity(value: { dev: number; ino: number }): FileIdentity {
  return { device: value.dev, inode: value.ino };
}

function sameIdentity(left: FileIdentity, right: FileIdentity): boolean {
  return left.device === right.device && left.inode === right.inode;
}

function isNotFound(error: unknown): boolean {
  return error !== null && typeof error === "object" && "code" in error && error.code === "ENOENT";
}

async function unlinkIfIdentity(path: string, expected: FileIdentity, filesystem: Readonly<ProfileCliRuntimeFilesystem>): Promise<void> {
  try {
    const details = await filesystem.lstat(path);
    if (!details.isFile() || details.isSymbolicLink() || !sameIdentity(identity(details), expected)) return;
    await filesystem.unlink(path);
  } catch (error) {
    if (!isNotFound(error)) throw error;
  }
}

async function syncDirectory(path: string, filesystem: Readonly<ProfileCliRuntimeFilesystem>): Promise<void> {
  const handle = await filesystem.open(path, constants.O_RDONLY);
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}

/** Internal runtime seam; the public CLI receives only ProfileCliIo.writeNewJson. */
export async function writeNewProfileJson(
  output: string,
  value: unknown,
  filesystem: Readonly<ProfileCliRuntimeFilesystem> = realProfileCliRuntimeFilesystem
): Promise<void> {
  const parent = dirname(output);
  const temporary = join(parent, `.${basename(output)}.tmp-${randomUUID()}`);
  let temporaryIdentity: FileIdentity | undefined;
  let publishedIdentity: FileIdentity | undefined;
  try {
    const handle = await filesystem.open(temporary, "wx", 0o600);
    try {
      await handle.writeFile(`${JSON.stringify(value, null, 2)}\n`, "utf8");
      await handle.sync();
      temporaryIdentity = identity(await handle.stat());
    } finally {
      await handle.close();
    }
    await filesystem.link(temporary, output);
    publishedIdentity = identity(await filesystem.lstat(output));
    if (temporaryIdentity === undefined || !sameIdentity(temporaryIdentity, publishedIdentity)) {
      throw new Error("PROFILE_OUTPUT_PUBLICATION_FAILED");
    }
    await syncDirectory(parent, filesystem);
    await unlinkIfIdentity(temporary, temporaryIdentity, filesystem);
    await syncDirectory(parent, filesystem);
  } catch (error) {
    if (publishedIdentity !== undefined) await unlinkIfIdentity(output, publishedIdentity, filesystem);
    if (temporaryIdentity !== undefined) await unlinkIfIdentity(temporary, temporaryIdentity, filesystem);
    throw error;
  }
}
