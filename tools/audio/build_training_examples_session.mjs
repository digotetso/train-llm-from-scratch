#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import process from "node:process";

const SAMPLE_RATE = 48_000;
const PROGRAM_END = 710;
const DEFAULT_GAP = 0.18;
const ROOM_TONE_IN = 71.2;
const ROOM_TONE_OUT = 83.8;
const SOURCE_END = 988.863896;

const sections = [
  {
    id: "00:00",
    name: "The AI We Are Going to Build",
    targetStart: 0,
    minimumLeadIn: 0,
    clips: [
      [911.98, 913.06, "Clean opening phrase"],
      [913.42, 926.96, "AI examples and new-text explanation"],
      [23.88, 70.14, "Course goal, LLM definition, training patterns, and one-sentence setup"],
    ],
  },
  {
    id: "01:00",
    name: "A Sentence You Can Finish",
    targetStart: 60,
    minimumLeadIn: 0.6,
    clips: [
      [93.78, 147.76, "Hot/cold prediction, next-word mental model, and lesson promise"],
    ],
  },
  {
    id: "01:50",
    name: "The Answer Is Already in the Sentence",
    targetStart: 110,
    minimumLeadIn: 0.6,
    clips: [
      [187.36, 241.78, "Training-data setup, familiar continuation, and hidden answer explanation"],
    ],
  },
  {
    id: "02:40",
    name: "Make One Example by Hand",
    targetStart: 160,
    minimumLeadIn: 0.6,
    clips: [
      [269.14, 275.6, "Complete sentence and cut placement"],
      [276.82, 285.58, "Input definition"],
      [286.84, 304.38, "Target definition and one training example"],
      [309.76, 315.78, "Full-chain explanation: sentence supplies input and target"],
      [316.28, 319.1, "The cut distinguishes the two parts"],
      [321.5, 324.22, "Nothing invented or manually labelled"],
      [330.78, 332.4, "One cut gives one example"],
      [338.06, 343.86, "The cut can move; the sentence has six words"],
      [348.1, 354.1, "Learner prediction: how many examples can we make?"],
    ],
  },
  {
    id: "03:50",
    name: "One Sentence, Five Examples",
    targetStart: 230,
    minimumLeadIn: 2.5,
    clips: [
      [355.78, 362.18, "Five-example answer and moving the cut"],
      [372.9, 385.0, "Input grows and the next word becomes the target"],
      [385.88, 393.9, "Five examples from one six-word sentence"],
      [405.56, 407.98, "Simplified pattern introduction"],
      [416.94, 420.4, "Examples equal words minus one"],
      [421.14, 431.1, "Why the first word cannot be a target example"],
      [433.1, 435.6, "Every later word can take a turn as target"],
      [436.38, 449.86, "One hundred words yield ninety-nine examples"],
      [452.32, 464.4, "Code scales the same rule"],
    ],
  },
  {
    id: "05:10",
    name: "Build the Examples in Python",
    targetStart: 310,
    minimumLeadIn: 0.8,
    clips: [
      [472.84, 476.42, "Ask Python to repeat the cuts"],
      [484.34, 489.74, "Split the sentence into six words"],
      [494.06, 506.12, "Start the loop at position one"],
      [511.4, 526.8, "Slice input, select target, print, and repeat"],
      [529.44, 531.76, "Same process as the hand-built example"],
      [537.28, 540.06, "Code only makes the process faster"],
      [542.94, 548.94, "Both parts come from the same list; no answer sheet"],
      [549.38, 555.1, "Prediction setup: how many example lines"],
      [556.3, 557.14, "Prediction completion: should it print?"],
      [561.06, 564.78, "Inputs grow from left to right"],
      [589.7, 598.82, "Introduce the compact shifted relationship"],
    ],
  },
  {
    id: "06:50",
    name: "The Same Sequence, Shifted One Place",
    targetStart: 410,
    minimumLeadIn: 8,
    clips: [
      [602.2, 606.68, "Start with the same six words and two rows"],
      [611.42, 617.16, "Remove the last word to make inputs"],
      [618.08, 623.28, "Remove the first word to make targets"],
      [625.18, 628.48, "Second row sits one position ahead"],
      [631.56, 636.18, "Each input aligns with the next word"],
      [638.38, 646.38, "shifted_targets.py and the first slice"],
      [652.34, 655.64, "The second slice removes the first word"],
      [674.56, 680.18, "zip pairs the aligned rows"],
      [686.74, 688.82, "This is not a different task"],
      [690.62, 698.42, "Same next-word relationship at every position"],
      [699.38, 704.18, "The same shift will later use numeric sequences"],
      [708.76, 721.26, "Prediction: input-only and target-only words"],
    ],
  },
  {
    id: "08:20",
    name: "Run, Observe, and Explain",
    targetStart: 500,
    minimumLeadIn: 8,
    clips: [
      [723.96, 735.56, "Run training_examples.py and observe five lines"],
      [750.76, 761.9, "Run shifted_targets.py and observe the offset"],
      [763.5, 770.1, "The appears only in the inputs"],
      [771.52, 777.12, "Cold appears only in the targets"],
      [783.06, 785.44, "The rule works for one sentence"],
      [785.44, 791.22, "Question whether the rule or example was memorized"],
      [791.9, 802.42, "Change the sentence, count, and predict", 2.5],
      [802.88, 813.44, "Run it and confirm five examples"],
      [814.04, 824.26, "The sentence changed; the rule did not"],
      [824.92, 828.94, "Transition to the intended two key points"],
    ],
  },
  {
    id: "10:10",
    name: "Two Key Points",
    targetStart: 610,
    minimumLeadIn: 5,
    clips: [
      [829.52, 838.76, "First: the target was already in the text"],
      [839.8, 853.08, "Second: one sentence produced five useful examples"],
    ],
  },
  {
    id: "11:00",
    name: "The Mental Model",
    targetStart: 660,
    minimumLeadIn: 5,
    clips: [
      [860.6, 868.54, "Sentence, cut, and input"],
      [870.06, 885.48, "Target and repeated examples"],
      [888.68, 889.7, "Closing: that is it"],
      [891.24, 896.94, "Training examples are created; next-lesson sign-off"],
    ],
  },
];

function secondsToSamples(seconds) {
  return Math.round(seconds * SAMPLE_RATE);
}

function xmlEscape(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function guidFor(seed) {
  const hash = createHash("sha256").update(seed).digest("hex").slice(0, 32);
  return `${hash.slice(0, 8)}-${hash.slice(8, 12)}-${hash.slice(12, 16)}-${hash.slice(16, 20)}-${hash.slice(20)}`;
}

function clipXml({
  id,
  name,
  sourceIn,
  sourceOut,
  outputIn,
  outputOut,
  muted = false,
  locked = false,
  looped = false,
}) {
  const start = secondsToSamples(outputIn);
  const end = secondsToSamples(outputOut);
  const sourceStart = secondsToSamples(sourceIn);
  const sourceEnd = secondsToSamples(sourceOut);
  const duration = end - start;
  const fadeLength = Math.min(240, Math.max(1, Math.floor(duration / 4)));
  const safeName = xmlEscape(name);

  return `
        <audioClip clipAutoCrossfade="true" crossFadeHeadClipID="-1" crossFadeTailClipID="-1" endPoint="${end}" fileID="0" hue="-1" id="${id}" lockedInTime="${locked}" looped="${looped}" name="${safeName}" offline="false" select="false" sourceInPoint="${sourceStart}" sourceOutPoint="${sourceEnd}" startPoint="${start}" zOrder="${id}">
          <component componentGuid="${guidFor(`gain-${id}`)}" componentID="Audition.Fader" id="clipGain" name="volume" powered="true">
            <parameter index="0" name="volume" parameterValue="1"/>
            <parameter index="1" name="static gain" parameterValue="1"/>
          </component>
          <component componentGuid="${guidFor(`mute-${id}`)}" componentID="Audition.Mute" id="clipMute" name="Mute" powered="true">
            <parameter index="0" parameterValue="${muted ? 1 : 0}"/>
            <parameter index="1" name="mute" parameterValue="${muted ? 1 : 0}"/>
          </component>
          <component id="clipPan" powered="true"/>
          <fadeIn crossFadeLinkType="linkedAsymmetric" endPoint="${fadeLength}" shape="0" startPoint="0" type="cosine"/>
          <fadeOut crossFadeLinkType="linkedAsymmetric" endPoint="${duration}" shape="0" startPoint="${duration - fadeLength}" type="cosine"/>
          <editParameter parameterIndex="0" slotIndex="4294967280"/>
          <channelMap>
            <channel index="0" sourceIndex="0"/>
          </channelMap>
        </audioClip>`;
}

function replaceTrack(xml, trackId, trackName, clipMarkup) {
  const startPattern = `<audioTrack automationLaneOpenState="false" id="${trackId}"`;
  const start = xml.indexOf(startPattern);
  if (start < 0) throw new Error(`Track ${trackId} not found`);
  const end = xml.indexOf("\n      </audioTrack>", start);
  if (end < 0) throw new Error(`Track ${trackId} end not found`);

  let track = xml.slice(start, end);
  track = track.replace(/<name>[^<]*<\/name>/, `<name>${xmlEscape(trackName)}</name>`);
  track = track.replace(/\n        <audioClip[\s\S]*?<\/audioClip>/g, "");
  track += clipMarkup;

  return xml.slice(0, start) + track + xml.slice(end);
}

function buildTimeline() {
  const dialogue = [];
  let previousEnd = 0;
  let clipId = 100;

  for (const section of sections) {
    const actualStart = Math.max(
      section.targetStart,
      previousEnd + section.minimumLeadIn,
    );
    let cursor = actualStart;

    section.actualStart = actualStart;
    for (let index = 0; index < section.clips.length; index += 1) {
      const [sourceIn, sourceOut, note, customGapAfter] = section.clips[index];
      const duration = sourceOut - sourceIn;
      const outputIn = cursor;
      const outputOut = outputIn + duration;
      dialogue.push({
        id: clipId,
        sectionId: section.id,
        sectionName: section.name,
        note,
        sourceIn,
        sourceOut,
        outputIn,
        outputOut,
      });
      clipId += 1;
      cursor = outputOut;
      if (index < section.clips.length - 1) {
        cursor += customGapAfter ?? DEFAULT_GAP;
      }
    }
    previousEnd = cursor;
    section.actualEnd = cursor;
  }

  return dialogue;
}

function findRoomToneHolds(dialogue) {
  const holds = [];
  const sorted = [...dialogue].sort((a, b) => a.outputIn - b.outputIn);
  let cursor = 0;

  for (const clip of sorted) {
    const gap = clip.outputIn - cursor;
    if (gap >= 0.5) {
      holds.push({
        outputIn: cursor,
        outputOut: clip.outputIn,
        note: "Intentional room-tone hold",
      });
    }
    cursor = Math.max(cursor, clip.outputOut);
  }

  if (PROGRAM_END - cursor >= 0.5) {
    holds.push({
      outputIn: cursor,
      outputOut: PROGRAM_END,
      note: "Closing room-tone hold",
    });
  }
  return holds;
}

function expandRoomToneHolds(holds) {
  const sourceDuration = ROOM_TONE_OUT - ROOM_TONE_IN;
  const segments = [];

  for (const [holdIndex, hold] of holds.entries()) {
    let cursor = hold.outputIn;
    let part = 1;
    while (hold.outputOut - cursor > 0.000_001) {
      const duration = Math.min(sourceDuration, hold.outputOut - cursor);
      segments.push({
        holdIndex,
        part,
        outputIn: cursor,
        outputOut: cursor + duration,
        sourceIn: ROOM_TONE_IN,
        sourceOut: ROOM_TONE_IN + duration,
      });
      cursor += duration;
      part += 1;
    }
  }
  return segments;
}

function validateTimeline(dialogue, holds) {
  let cursor = 0;
  for (const clip of dialogue) {
    if (
      clip.sourceIn < 0 ||
      clip.sourceOut <= clip.sourceIn ||
      clip.sourceOut > SOURCE_END
    ) {
      throw new Error(`Invalid source range for clip ${clip.id}`);
    }
    if (
      clip.outputIn < cursor ||
      clip.outputOut <= clip.outputIn ||
      clip.outputOut > PROGRAM_END
    ) {
      throw new Error(`Invalid or overlapping output range for clip ${clip.id}`);
    }
    cursor = clip.outputOut;
  }

  for (const hold of holds) {
    if (
      hold.outputIn < 0 ||
      hold.outputOut <= hold.outputIn ||
      hold.outputOut > PROGRAM_END
    ) {
      throw new Error("Invalid room-tone hold");
    }
    const overlapsDialogue = dialogue.some(
      (clip) =>
        clip.outputIn < hold.outputOut && clip.outputOut > hold.outputIn,
    );
    if (overlapsDialogue) {
      throw new Error("Room-tone hold overlaps retained dialogue");
    }
  }
}

function buildEdlMarkdown(dialogue, holds) {
  const lines = [
    "# Training Examples Narration Edit Decision List",
    "",
    "Editorial authority: source-led coherence. The production script is a structural and timing reference; intentional recorded changes such as “two key points” are retained.",
    "",
    "| ID | Section | Source in | Source out | Output in | Output out | Decision | Notes |",
    "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
  ];

  for (const clip of dialogue) {
    lines.push(
      `| D${clip.id} | ${clip.sectionId} ${clip.sectionName} | ${clip.sourceIn.toFixed(3)} | ${clip.sourceOut.toFixed(3)} | ${clip.outputIn.toFixed(3)} | ${clip.outputOut.toFixed(3)} | KEEP | ${clip.note} |`,
    );
  }
  for (let index = 0; index < holds.length; index += 1) {
    const hold = holds[index];
    lines.push(
      `| RT${String(index + 1).padStart(2, "0")} | Room tone | ${ROOM_TONE_IN.toFixed(3)} | ${ROOM_TONE_OUT.toFixed(3)} | ${hold.outputIn.toFixed(3)} | ${hold.outputOut.toFixed(3)} | ROOM-TONE | ${hold.note} |`,
    );
  }

  lines.push(
    "",
    "## Removed material",
    "",
    "- All abandoned starts and repeated takes not represented by a `KEEP` row.",
    "- The incomplete restart from source `898.800` to source end.",
    "- Long accidental recording gaps outside the intentional output holds.",
    "",
    "## Section timing",
    "",
    "| Reference | Section | Actual output start | Actual output end |",
    "| ---: | --- | ---: | ---: |",
  );
  for (const section of sections) {
    lines.push(
      `| ${section.id} | ${section.name} | ${section.actualStart.toFixed(3)} | ${section.actualEnd.toFixed(3)} |`,
    );
  }
  lines.push("", `Program end: ${PROGRAM_END.toFixed(3)} seconds.`);
  return `${lines.join("\n")}\n`;
}

function buildFfmpegFilter(dialogue, holds) {
  const chains = [];
  const labels = [];
  let labelIndex = 0;

  for (const clip of dialogue) {
    const durationSamples =
      secondsToSamples(clip.sourceOut) - secondsToSamples(clip.sourceIn);
    const label = `a${labelIndex}`;
    labels.push(`[${label}]`);
    chains.push(
      `[0:a]atrim=start_sample=${secondsToSamples(clip.sourceIn)}:end_sample=${secondsToSamples(clip.sourceOut)},asetpts=PTS-STARTPTS,afade=t=in:ss=0:ns=240,afade=t=out:ss=${durationSamples - 240}:ns=240,adelay=${secondsToSamples(clip.outputIn)}S:all=1[${label}]`,
    );
    labelIndex += 1;
  }

  for (const hold of holds) {
    const durationSamples =
      secondsToSamples(hold.outputOut) - secondsToSamples(hold.outputIn);
    const sourceDurationSamples =
      secondsToSamples(ROOM_TONE_OUT) - secondsToSamples(ROOM_TONE_IN);
    const label = `a${labelIndex}`;
    labels.push(`[${label}]`);
    chains.push(
      `[0:a]atrim=start_sample=${secondsToSamples(ROOM_TONE_IN)}:end_sample=${secondsToSamples(ROOM_TONE_OUT)},asetpts=PTS-STARTPTS,aloop=loop=-1:size=${sourceDurationSamples}:start=0,atrim=end_sample=${durationSamples},afade=t=in:ss=0:ns=240,afade=t=out:ss=${durationSamples - 240}:ns=240,adelay=${secondsToSamples(hold.outputIn)}S:all=1[${label}]`,
    );
    labelIndex += 1;
  }

  chains.push(
    `${labels.join("")}amix=inputs=${labels.length}:duration=longest:normalize=0,atrim=end_sample=${secondsToSamples(PROGRAM_END)}[out]`,
  );
  return `${chains.join(";\n")}\n`;
}

async function main() {
  const [
    basePath,
    outputSessionPath,
    outputEdlPath,
    outputManifestPath,
    mediaAbsolutePath,
    mediaRelativePath,
    outputFilterPath,
  ] = process.argv.slice(2);
  if (!basePath || !outputSessionPath || !outputEdlPath || !outputManifestPath) {
    throw new Error(
      "Usage: build_training_examples_session.mjs BASE_SESX OUTPUT_SESX OUTPUT_EDL OUTPUT_MANIFEST",
    );
  }

  const dialogue = buildTimeline();
  const holds = findRoomToneHolds(dialogue);
  validateTimeline(dialogue, holds);
  const roomToneSegments = expandRoomToneHolds(holds);
  let xml = await readFile(basePath, "utf8");

  const dialogueMarkup = dialogue
    .map((clip) =>
      clipXml({
        id: clip.id,
        name: `VO ${clip.sectionId} ${clip.note}`,
        sourceIn: clip.sourceIn,
        sourceOut: clip.sourceOut,
        outputIn: clip.outputIn,
        outputOut: clip.outputOut,
      }),
    )
    .join("");
  const roomToneMarkup = roomToneSegments
    .map((segment, index) =>
      clipXml({
        id: 500 + index,
        name: `ROOM TONE ${segment.holdIndex + 1}.${segment.part}`,
        sourceIn: segment.sourceIn,
        sourceOut: segment.sourceOut,
        outputIn: segment.outputIn,
        outputOut: segment.outputOut,
        locked: true,
      }),
    )
    .join("");
  const referenceMarkup = clipXml({
    id: 900,
    name: "SOURCE REFERENCE (MUTED)",
    sourceIn: 0,
    sourceOut: PROGRAM_END,
    outputIn: 0,
    outputOut: PROGRAM_END,
    muted: true,
    locked: true,
  });

  xml = xml.replace(
    /(<session\b[^>]*\bduration=")[^"]+(")/,
    `$1${secondsToSamples(PROGRAM_END)}$2`,
  );
  xml = replaceTrack(xml, "10001", "VO EDIT", dialogueMarkup);
  xml = replaceTrack(xml, "10002", "ROOM TONE", roomToneMarkup);
  xml = replaceTrack(xml, "10003", "SOURCE REFERENCE", referenceMarkup);
  if (mediaAbsolutePath) {
    xml = xml.replace(
      /(<file\b[^>]*\babsolutePath=")[^"]+(")/,
      `$1${xmlEscape(mediaAbsolutePath)}$2`,
    );
  }
  if (mediaRelativePath) {
    xml = xml.replace(
      /(<file\b[^>]*\brelativePath=")[^"]+(")/,
      `$1${xmlEscape(mediaRelativePath)}$2`,
    );
  }

  await writeFile(outputSessionPath, xml, "utf8");
  await writeFile(outputEdlPath, buildEdlMarkdown(dialogue, holds), "utf8");
  await writeFile(
    outputManifestPath,
    `${JSON.stringify(
      {
        sampleRate: SAMPLE_RATE,
        programEnd: PROGRAM_END,
        editorialAuthority: "source-led coherence; script as reference",
        dialogue,
        roomToneHolds: holds,
        sections: sections.map(
          ({ id, name, targetStart, actualStart, actualEnd }) => ({
            id,
            name,
            targetStart,
            actualStart,
            actualEnd,
          }),
        ),
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  if (outputFilterPath) {
    await writeFile(outputFilterPath, buildFfmpegFilter(dialogue, holds), "utf8");
  }
}

await main();
