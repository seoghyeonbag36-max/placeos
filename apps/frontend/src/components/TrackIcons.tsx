/* 트랙 아이콘 — 라이브러리를 더 붙이지 않는다(지도 SDK 만으로도 이미 무겁다).
   currentColor 라 활성/비활성 색이 버튼 상태 하나로 따라온다.
   2026-10-08: App.tsx 의 레일 아이콘을 여기로 옮겼다 — 랜딩(pages/Landing)이 같은 그림을 써야 하고,
   복사하면 한쪽만 고쳐져 레일과 랜딩의 아이콘이 어긋난다. */
const SVG = {
  fill: "none", stroke: "currentColor", strokeWidth: 1.7,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24", "aria-hidden": true,
};

/* Platform — 모델(LSTM·GNN) 축을 뜻하는 노드+스파크 */
export function IconSpark() {
  return (
    <svg {...SVG}>
      <circle cx="6" cy="17" r="2.2" />
      <circle cx="12.5" cy="9" r="2.2" />
      <circle cx="19" cy="15" r="2.2" />
      <path d="m7.6 15.3 3.5-4.4m3 .3 3.3 3" />
    </svg>
  );
}

export function IconPin() {
  return (
    <svg {...SVG}>
      <path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.6" />
    </svg>
  );
}

/* Posting — 빈 자리에 들어간다는 뜻의 열쇠 */
export function IconKey() {
  return (
    <svg {...SVG}>
      <circle cx="8" cy="15" r="3.4" />
      <path d="m10.5 12.5 8-8" />
      <path d="m16.5 6.5 2 2" />
      <path d="m14 9 2 2" />
    </svg>
  );
}

/* 계정 — 사람 머리와 어깨 */
export function IconUser() {
  return (
    <svg {...SVG}>
      <circle cx="12" cy="8" r="3.6" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </svg>
  );
}

/* Program — 검증 program 을 알린다는 뜻의 확성기 */
export function IconMegaphone() {
  return (
    <svg {...SVG}>
      <path d="M4 10v4a1 1 0 0 0 1 1h3l7 4V5L8 9H5a1 1 0 0 0-1 1Z" />
      <path d="M18.5 9.5a3.5 3.5 0 0 1 0 5" />
    </svg>
  );
}
