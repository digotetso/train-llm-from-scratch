export type BridgeWorkCancellationReason = "deadline" | "shutdown";
export type BridgeWorkPhase = "copy" | "fingerprint" | "parse";

export interface BridgeWorkProgress {
  bytesProcessed: number;
  phase: BridgeWorkPhase;
}

export interface BridgeWorkContext {
  checkpoint?: (progress: BridgeWorkProgress) => Promise<void> | void;
  deadlineSignal?: AbortSignal;
  onCancellation?: (reason: BridgeWorkCancellationReason) => void;
  shutdownSignal?: AbortSignal;
}

export class BridgeWorkDeadlineError extends Error {
  constructor() {
    super("Bridge export work exceeded its deadline");
    this.name = "BridgeWorkDeadlineError";
  }
}

export class BridgeWorkShutdownError extends Error {
  constructor() {
    super("Bridge export work stopped for shutdown");
    this.name = "BridgeWorkShutdownError";
  }
}

function cancellationReason(context: BridgeWorkContext | undefined): BridgeWorkCancellationReason | undefined {
  if (context?.shutdownSignal?.aborted === true) return "shutdown";
  if (context?.deadlineSignal?.aborted === true) return "deadline";
  return undefined;
}

function cancellationError(reason: BridgeWorkCancellationReason): Error {
  return reason === "shutdown" ? new BridgeWorkShutdownError() : new BridgeWorkDeadlineError();
}

export function observeBridgeWorkCancellation(
  context: BridgeWorkContext | undefined
): BridgeWorkCancellationReason | undefined {
  const reason = cancellationReason(context);
  if (reason !== undefined) context?.onCancellation?.(reason);
  return reason;
}

function throwIfCancelled(context: BridgeWorkContext | undefined): void {
  const reason = observeBridgeWorkCancellation(context);
  if (reason !== undefined) throw cancellationError(reason);
}

export async function checkpointBridgeWork(
  context: BridgeWorkContext | undefined,
  phase: BridgeWorkPhase,
  bytesProcessed: number
): Promise<void> {
  if (!Number.isSafeInteger(bytesProcessed) || bytesProcessed < 0) {
    throw new TypeError("Bridge work progress must be a non-negative safe integer");
  }
  throwIfCancelled(context);
  if (context?.checkpoint === undefined) return;

  await new Promise<void>((resolve, reject) => {
    let settled = false;
    const finish = (operation: () => void): void => {
      if (settled) return;
      settled = true;
      context.deadlineSignal?.removeEventListener("abort", onAbort);
      context.shutdownSignal?.removeEventListener("abort", onAbort);
      operation();
    };
    const onAbort = (): void => {
      const reason = observeBridgeWorkCancellation(context);
      if (reason !== undefined) finish(() => reject(cancellationError(reason)));
    };
    context.deadlineSignal?.addEventListener("abort", onAbort, { once: true });
    context.shutdownSignal?.addEventListener("abort", onAbort, { once: true });
    let checkpointResult: Promise<void> | void;
    try {
      checkpointResult = context.checkpoint?.({ bytesProcessed, phase });
    } catch (error) {
      finish(() => reject(error));
      return;
    }
    Promise.resolve(checkpointResult).then(
      () => finish(resolve),
      (error: unknown) => finish(() => reject(error))
    );
    onAbort();
  });
  throwIfCancelled(context);
}
