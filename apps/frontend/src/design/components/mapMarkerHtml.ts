/**
 * 지도 위 공실 점(red dot)의 HTML. 네이버 SDK `icon.content` 에 그대로 넣는다.
 * 흰 테두리 + 이중 그림자는 위성/일반 지도 어느 배경에서도 점이 묻히지 않게 한다.
 */
export function vacancyDotHTML(color: string, size = 13, hot = false): string {
  // hot = 목록에서 이 건물에 마우스를 올린 상태(지도↔목록 호버 동기화, 2026-09-13).
  // **크기를 키우지 않는다** — 점이 커지면 이웃 점을 덮어 주변 밀도가 달라 보인다.
  // 대신 테두리를 두껍게 하고 불투명하게 올린다. 위치도 모양도 그대로다.
  // → design/references/INDEX.md §2-3(Zillow·Redfin 호버 동기화)
  const ring = hot ? 3 : 1.5;
  const shadow = hot
    ? "0 0 0 2px rgba(28,37,51,.55),0 2px 6px rgba(0,0,0,.45)"
    : "0 0 0 1px rgba(0,0,0,.12),0 1px 3px rgba(0,0,0,.35)";
  return (
    `<div style="width:${size}px;height:${size}px;border-radius:50%;`
    + `background:${color};border:${ring}px solid #fff;`
    + `box-shadow:${shadow};opacity:${hot ? 1 : 0.92}"></div>`
  );
}

/** 점의 앵커 오프셋 — 테두리 1.5px 를 포함한 중심. SDK 의 `icon.anchor` 에 쓴다. */
export const vacancyDotAnchor = (size = 13) => size / 2 + 1.5;

/** HTML 문자열에 사용자·데이터 문자열을 넣기 전에 반드시 거친다(건물명에 `<` 가 온다). */
export function escapeHTML(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}

/**
 * 지도 위 **라벨 칩** — 금액·업종처럼 "값을 글자로 말해야 하는" 마커(2026-09-13).
 *
 * 공실 점은 색이 곧 값이라 글자가 없어도 되지만, 임대시세·입점 자리는 **숫자가 답**이다.
 * 색 칸으로 칠하면 "진한 곳이 비싸다"만 남고 "얼마냐"가 사라진다(종전 임대 격자가 그랬다).
 * 호갱노노·직방이 지도 위에 가격 말풍선을 거는 것과 같은 자리다.
 *
 * - `color` 는 칩 테두리·꼬리 색이다. 트랙 색이나 공실 색을 그대로 넘긴다(여기서 짓지 않는다).
 * - `active`(선택) 는 칩을 색으로 채운다. `hot`(호버) 은 잉크 테두리만 올린다 —
 *   선택은 상태고 호버는 순간이라 같은 모양이면 둘이 구별되지 않는다(MapShell R1 과 같은 규칙).
 * - `dashed` 는 추정(probable) 표시다. 확정과 같은 모양으로 그리면 추정이 실측처럼 읽힌다.
 */
export function mapLabelHTML({ text, sub, color, active = false, hot = false, dashed = false }: {
  text: string; sub?: string; color: string; active?: boolean; hot?: boolean; dashed?: boolean;
}): string {
  const bg = active ? color : "#fff";
  const fg = active ? "#fff" : "#1C2533";
  const border = hot ? "#1C2533" : color;
  const subColor = active ? "rgba(255,255,255,.85)" : "#6B7280";
  return (
    `<div style="position:relative;transform:translate(-50%,-100%);display:inline-flex;flex-direction:column;align-items:center;`
    + `font-family:Pretendard,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;cursor:pointer;white-space:nowrap">`
    + `<div style="display:flex;align-items:baseline;gap:4px;padding:3px 7px;border-radius:8px;background:${bg};color:${fg};`
    + `border:${hot ? 2 : 1.5}px ${dashed ? "dashed" : "solid"} ${border};`
    + `box-shadow:0 1px 4px rgba(11,27,51,.28);font-size:12px;font-weight:700;line-height:1.25;font-variant-numeric:tabular-nums">`
    + `${escapeHTML(text)}${sub ? `<span style="font-size:10.5px;font-weight:600;color:${subColor}">${escapeHTML(sub)}</span>` : ""}</div>`
    + `<div style="width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:6px solid ${border};margin-top:-1px"></div>`
    + `</div>`
  );
}

/** 만원 단위 금액을 지도 칩 길이로 줄인다 — 12,345 → "1.2억", 740 → "740만". */
export function shortManwon(v: number): string {
  if (v >= 10000) {
    const eok = v / 10000;
    return `${eok >= 10 ? Math.round(eok) : Number(eok.toFixed(1))}억`;
  }
  return `${Math.round(v).toLocaleString("ko-KR")}만`;
}
