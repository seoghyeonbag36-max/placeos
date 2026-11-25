/* 업종 아이콘 — 질문 흐름의 업종 타일이 이모지 대신 쓴다(2026-11-25).
   이모지는 OS·브라우저마다 그림이 달라 타일이 들쭉날쭉했고, 색이 고정이라 선택 상태(.is-on)를 따라오지 못했다.
   TrackIcons 와 같은 규격(24px 격자 · 스트로크 · currentColor)이라 라이브러리를 더 붙이지 않는다.
   그림은 장식이다 — 타일에 업종 이름이 함께 읽히므로 aria-hidden. */
import type { ReactNode } from "react";

const SVG = {
  fill: "none", stroke: "currentColor", strokeWidth: 1.7,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24", "aria-hidden": true,
};

/** 업종 key → 그림. 목록에 없는 key 는 `fallback`(백화점 모양)으로 간다. */
const PATHS: Record<string, ReactNode> = {
  // 카페 — 김이 오르는 잔
  cafe: <>
    <path d="M5 9h11v5a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4V9Z" />
    <path d="M16 10.5h1.5a2 2 0 0 1 0 4H16" />
    <path d="M8.5 3.5c0 1 .8 1.2.8 2.2M12 3.5c0 1 .8 1.2.8 2.2" />
  </>,
  // 음식점 — 포크와 나이프
  restaurant: <>
    <path d="M6 3v6a2 2 0 0 0 4 0V3M8 3v18" />
    <path d="M17 21V3c-2.2 1.6-3.4 4.4-3.4 8H17" />
  </>,
  // 술집 — 칵테일 잔
  bar: <>
    <path d="M5 4h14l-7 8-7-8Z" />
    <path d="M12 12v8M8 20h8" />
  </>,
  // 미용 — 가위
  beauty: <>
    <circle cx="6.5" cy="6.5" r="2.5" />
    <circle cx="6.5" cy="17.5" r="2.5" />
    <path d="M8.2 8.2 20 19M8.2 15.8 20 5" />
  </>,
  // 의원 — 십자
  clinic: <>
    <rect x="4" y="4" width="16" height="16" rx="3" />
    <path d="M12 8v8M8 12h8" />
  </>,
  // 약국 — 알약
  pharmacy: <>
    <rect x="3" y="9" width="18" height="6" rx="3" transform="rotate(-45 12 12)" />
    <path d="m9.6 9.6 4.8 4.8" />
  </>,
  // 편의점 — 차양이 있는 가게
  convenience: <>
    <path d="M4 9.5 5.5 4h13L20 9.5" />
    <path d="M4 9.5a2.7 2.7 0 0 0 5.3 0 2.7 2.7 0 0 0 5.4 0 2.7 2.7 0 0 0 5.3 0" />
    <path d="M5.5 12.5V20h13v-7.5M10 20v-4h4v4" />
  </>,
  // 패션 — 티셔츠
  fashion: <path d="m8.5 4-5 3 2 4 2.5-1.2V20h8v-10.2l2.5 1.2 2-4-5-3a3.5 3.5 0 0 1-7 0Z" />,
  // 교육 — 책
  education: <>
    <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H19v13H5.5A1.5 1.5 0 0 0 4 18.5v-13Z" />
    <path d="M4 18.5A1.5 1.5 0 0 0 5.5 20H19v-3" />
  </>,
  // 운동 — 덤벨
  fitness: <path d="M3 10v4M6 8v8M18 8v8M21 10v4M6 12h12" />,
  // 숙박 — 침대
  lodging: <>
    <path d="M3 18V7M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5" />
    <circle cx="7" cy="11" r="1.8" />
  </>,
  // 문화 — 팔레트
  culture: <>
    <path d="M12 4a8 8 0 1 0 0 16c1.2 0 1.8-.9 1.4-1.9-.4-1 .2-2.1 1.3-2.1H17a3 3 0 0 0 3-3C20 7.6 16.4 4 12 4Z" />
    <circle cx="8" cy="11" r=".9" />
    <circle cx="12" cy="8" r=".9" />
    <circle cx="16" cy="10.5" r=".9" />
  </>,
  // 기타 — 직접 적기(연필)
  other: <>
    <path d="m4 20 1-4L16.5 4.5a2 2 0 0 1 3 3L8 19l-4 1Z" />
    <path d="m14.5 6.5 3 3" />
  </>,
};

/** 모르는 key — 건물 */
const FALLBACK: ReactNode = <>
  <path d="M5 20V5h9v15M14 10h5v10M3 20h18" />
  <path d="M8 8.5h3M8 12h3M8 15.5h3" />
</>;

export default function IndustryIcon({ industryKey }: { industryKey: string }) {
  return <svg {...SVG}>{PATHS[industryKey] ?? FALLBACK}</svg>;
}
