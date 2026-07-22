import assert from "node:assert/strict";
import test from "node:test";
import {
  BridgeWorkDeadlineError,
  BridgeWorkShutdownError,
  checkpointBridgeWork
} from "../src/bridge/work-control.ts";

test("work checkpoints interrupt an injected slow phase when its deadline aborts", async () => {
  const deadline = new AbortController();
  let markStarted: (() => void) | undefined;
  const started = new Promise<void>((resolve) => { markStarted = resolve; });
  const never = new Promise<void>(() => {});
  let cancellation: string | undefined;
  const pending = checkpointBridgeWork({
    deadlineSignal: deadline.signal,
    checkpoint: ({ bytesProcessed, phase }) => {
      assert.deepEqual({ bytesProcessed, phase }, { bytesProcessed: 64 * 1024, phase: "parse" });
      markStarted?.();
      return never;
    },
    onCancellation: (reason) => { cancellation = reason; }
  }, "parse", 64 * 1024);

  await started;
  deadline.abort();

  await assert.rejects(pending, (error: unknown) => error instanceof BridgeWorkDeadlineError);
  assert.equal(cancellation, "deadline");
});

test("shutdown takes precedence when both work signals are aborted", async () => {
  const deadline = new AbortController();
  const shutdown = new AbortController();
  deadline.abort();
  shutdown.abort();

  await assert.rejects(
    checkpointBridgeWork({ deadlineSignal: deadline.signal, shutdownSignal: shutdown.signal }, "copy", 0),
    (error: unknown) => error instanceof BridgeWorkShutdownError
  );
});

test("a synchronous checkpoint failure removes cancellation listeners", async () => {
  const deadline = new AbortController();
  const checkpointFailure = new Error("checkpoint observer failed");
  let cancellationCalls = 0;

  await assert.rejects(
    checkpointBridgeWork({
      checkpoint: () => { throw checkpointFailure; },
      deadlineSignal: deadline.signal,
      onCancellation: () => { cancellationCalls += 1; }
    }, "parse", 1),
    (error: unknown) => error === checkpointFailure
  );
  deadline.abort();
  assert.equal(cancellationCalls, 0);
});
