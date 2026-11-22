/**
 * 배치도 사진 준비 — 건물주가 고른 사진을 **이 브라우저 안에서** 줄이고 다시 그려 JPEG 으로 만든다(2026-11-22).
 *
 * 왜 다시 그리나: 폰 사진은 수 MB 이고 촬영 위치·기기 정보(EXIF)가 들어 있다. 캔버스에 다시 그리면 그 정보가 사라지고 크기도 준다.
 * 서버는 이것을 믿지 않고 형식·크기를 다시 보고 메타데이터를 한 번 더 뗀다(services/direct_floor_plans) — 여기는 올리는 사람을 위한 편의다.
 */
export const FLOOR_PLAN_MAX_SIDE = 1600;       // 긴 변 상한(px) — 배치도 글씨가 읽히면서 보통 0.3~0.6MB
export const FLOOR_PLAN_QUALITY = 0.85;
export const FLOOR_PLAN_MAX_INPUT_BYTES = 25_000_000;   // 고른 원본이 이보다 크면 읽지 않는다(브라우저가 멎지 않게)

export interface PreparedFloorPlan { mime: "image/jpeg"; data: string; width: number; height: number; previewUrl: string; bytes: number }

/** 가로·세로를 긴 변이 `max` 이하가 되게 줄인 크기(키우지 않는다). */
export function fitWithin(width: number, height: number, max = FLOOR_PLAN_MAX_SIDE): { width: number; height: number } {
  const long = Math.max(width, height);
  if (long <= max) return { width, height };
  const k = max / long;
  return { width: Math.max(1, Math.round(width * k)), height: Math.max(1, Math.round(height * k)) };
}

async function decode(file: Blob): Promise<{ source: CanvasImageSource; width: number; height: number; close: () => void }> {
  if (typeof createImageBitmap === "function") {
    // imageOrientation: from-image — 폰으로 세워 찍은 사진이 누워 보이지 않게 EXIF 방향을 반영해 읽는다
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    return { source: bmp, width: bmp.width, height: bmp.height, close: () => bmp.close() };
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return { source: img, width: img.naturalWidth, height: img.naturalHeight, close: () => {} };
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** 파일 → 줄인 JPEG(base64). 읽을 수 없는 파일이면 사람이 읽는 문장으로 던진다. */
export async function prepareFloorPlan(file: File): Promise<PreparedFloorPlan> {
  if (!/^image\/(jpeg|png|webp|heic|heif)$/i.test(file.type) && !/\.(jpe?g|png|webp)$/i.test(file.name)) {
    throw new Error("사진 파일(JPEG·PNG)을 골라 주세요.");
  }
  if (file.size > FLOOR_PLAN_MAX_INPUT_BYTES) throw new Error("사진이 너무 커요. 25MB 이하로 골라 주세요.");
  let decoded: Awaited<ReturnType<typeof decode>>;
  try { decoded = await decode(file); } catch { throw new Error("이 사진을 읽지 못했어요. JPEG 또는 PNG 사진으로 다시 골라 주세요."); }
  try {
    const { width, height } = fitWithin(decoded.width, decoded.height);
    if (Math.min(width, height) < 100) throw new Error("사진이 너무 작아요. 변마다 100px 이상인 사진을 골라 주세요.");
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("이 브라우저에서는 사진을 줄일 수 없어요.");
    ctx.fillStyle = "#fff";                                   // 투명 PNG 가 검게 변하지 않게
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(decoded.source, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", FLOOR_PLAN_QUALITY));
    if (!blob) throw new Error("사진을 줄이지 못했어요. 다른 사진으로 다시 시도해 주세요.");
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    return { mime: "image/jpeg", data: btoa(binary), width, height, previewUrl: URL.createObjectURL(blob), bytes: bytes.length };
  } finally {
    decoded.close();
  }
}
