/**
 * 인스타그램 칸의 상태 문장 — Platform 의 인스타 칸(InstagramPanel)과 검색어 링크 칸이 **같은 판정**을 쓴다(2026-11-22 리뷰 반영:
 * 검색어 칸이 「수집 안 됨」을 늘 「연결 전」이라고 말해, 연결된 뒤 차례를 기다리는 상권에서 사실과 어긋났다).
 */
import type { InstagramTag } from "./api";

/** 수치가 없는 이유 — 연결 전 / 해시태그 없음 / 받지 못함 / 차례 대기. 수집된 상권이면 null */
export function instagramPendingReason(d: InstagramTag): string | null {
  if (d.status === "collected") return null;
  if (!d.connected) return "인스타그램 공식 API 연결 전이라 아직 수치가 없어요.";
  if (d.status === "no_hashtag") return `인스타그램에서 「#${d.hashtag}」 해시태그를 찾지 못했어요.`;
  if (d.status === "error") return "이 해시태그는 인스타그램이 검색을 막았거나 받지 못했어요.";
  return "공식 API 는 7일에 해시태그 30개만 검색할 수 있어 상권을 차례로 모으고 있어요 — 이 상권은 아직 차례가 오지 않았어요.";
}

/** 검색어 링크 칸의 한 문장 — 인스타 칸이 없으면(Gold 없음) 연결 전으로 말한다 */
export function instagramSearchNote(d: InstagramTag | null | undefined): string {
  if (d?.status === "collected") {
    return "인스타그램 수치는 「상권 특성 자세히 보기」의 인스타그램 칸에 있어요(공식 API · 대표 해시태그 하나 기준) — 아래 인스타 링크는 단어별 태그 페이지예요.";
  }
  if (d?.connected) {
    return `인스타그램은 대표 해시태그(#${d.hashtag}) 하나만 공식 API 로 모아요 — ${instagramPendingReason(d)} 아래는 단어별 태그 링크예요.`;
  }
  return "인스타그램은 공식 API 연결 전이라 단어별 수치가 없고 태그 링크만 드립니다.";
}
