/** TextEncoder-compatible UTF-8 byte length without browser-only globals. */
export function utf8ByteLength(value: string): number {
  let bytes = 0;
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit <= 0x7f) {
      bytes += 1;
    } else if (codeUnit <= 0x7ff) {
      bytes += 2;
    } else if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (next >= 0xdc00 && next <= 0xdfff) {
        bytes += 4;
        index += 1;
      } else {
        bytes += 3;
      }
    } else {
      bytes += 3;
    }
  }
  return bytes;
}

/** UTF-8 encoding without relying on the browser-only TextEncoder global. */
export function encodeUtf8(value: string): Uint8Array {
  const result = new Uint8Array(utf8ByteLength(value));
  let offset = 0;
  for (let index = 0; index < value.length; index += 1) {
    const first = value.charCodeAt(index);
    let codePoint = first;
    if (first >= 0xd800 && first <= 0xdbff) {
      const second = value.charCodeAt(index + 1);
      if (second >= 0xdc00 && second <= 0xdfff) {
        codePoint = 0x10000 + ((first - 0xd800) << 10) + (second - 0xdc00);
        index += 1;
      } else {
        codePoint = 0xfffd;
      }
    } else if (first >= 0xdc00 && first <= 0xdfff) {
      codePoint = 0xfffd;
    }
    if (codePoint <= 0x7f) {
      result[offset++] = codePoint;
    } else if (codePoint <= 0x7ff) {
      result[offset++] = 0xc0 | (codePoint >> 6);
      result[offset++] = 0x80 | (codePoint & 0x3f);
    } else if (codePoint <= 0xffff) {
      result[offset++] = 0xe0 | (codePoint >> 12);
      result[offset++] = 0x80 | ((codePoint >> 6) & 0x3f);
      result[offset++] = 0x80 | (codePoint & 0x3f);
    } else {
      result[offset++] = 0xf0 | (codePoint >> 18);
      result[offset++] = 0x80 | ((codePoint >> 12) & 0x3f);
      result[offset++] = 0x80 | ((codePoint >> 6) & 0x3f);
      result[offset++] = 0x80 | (codePoint & 0x3f);
    }
  }
  return result;
}

/** Strict UTF-8 decoding without relying on browser-only TextDecoder globals. */
export function decodeUtf8(bytes: Uint8Array): string {
  let result = "";
  for (let index = 0; index < bytes.length;) {
    const first = bytes[index]!;
    let codePoint: number;
    let continuationCount: number;
    if (first <= 0x7f) {
      codePoint = first;
      continuationCount = 0;
    } else if (first >= 0xc2 && first <= 0xdf) {
      codePoint = first & 0x1f;
      continuationCount = 1;
    } else if (first >= 0xe0 && first <= 0xef) {
      codePoint = first & 0x0f;
      continuationCount = 2;
    } else if (first >= 0xf0 && first <= 0xf4) {
      codePoint = first & 0x07;
      continuationCount = 3;
    } else {
      throw new TypeError("Invalid UTF-8 leading byte");
    }
    if (index + continuationCount >= bytes.length) throw new TypeError("Truncated UTF-8 sequence");
    for (let offset = 1; offset <= continuationCount; offset += 1) {
      const continuation = bytes[index + offset]!;
      if ((continuation & 0xc0) !== 0x80) throw new TypeError("Invalid UTF-8 continuation byte");
      codePoint = (codePoint << 6) | (continuation & 0x3f);
    }
    if (
      (continuationCount === 2 && codePoint < 0x800) ||
      (continuationCount === 3 && codePoint < 0x10000) ||
      (codePoint >= 0xd800 && codePoint <= 0xdfff) ||
      codePoint > 0x10ffff
    ) throw new TypeError("Invalid UTF-8 code point");
    result += codePoint <= 0xffff
      ? String.fromCharCode(codePoint)
      : String.fromCharCode(
        0xd800 + ((codePoint - 0x10000) >> 10),
        0xdc00 + ((codePoint - 0x10000) & 0x3ff)
      );
    index += continuationCount + 1;
  }
  return result;
}
