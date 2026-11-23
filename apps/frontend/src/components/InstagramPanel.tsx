/**
 * Platform 「밖에서 뭐라고 불리나」 — 인스타그램 칸(2026-11-22 · 사용자 결정 「인스타그램 데이터도 수집할 것」).
 *
 * 공식 Instagram Graph API 해시태그 검색의 **집계**만 보인다(data/collectors/instagram_hashtags.py) — 계정·본문·링크는 없다.
 * 공식 API 는 해시태그의 전체 게시물 수를 주지 않는다 → 「최근 24시간 표본」이라고 밝히고, 상한에서 끊겼으면 「이상」을 붙인다.
 * 수집 전(공식 API 연결 전 · 7일 30태그 한도로 차례 대기)이면 수치를 짓지 않고 그 이유와 태그 링크만 보인다.
 */
import { useState } from "react";
import type { InstagramTag } from "@/lib/api";
import { instagramPendingReason } from "@/lib/instagram";

const MEDIA_LABEL: Record<string, string> = { IMAGE: "사진", VIDEO: "영상", CAROUSEL_ALBUM: "여러 장" };
const DAY_MS = 86_400_000;

export default function InstagramPanel({ data, now: nowProp }: { data: InstagramTag; now?: number }) {
  // 「30일이 지났나」의 기준 시각 — 처음 그릴 때 한 번만 잰다(렌더마다 시계를 읽지 않는다)
  const [now] = useState(() => nowProp ?? Date.now());
  const tagUrl = `https://www.instagram.com/explore/tags/${encodeURIComponent(data.hashtag)}/`;
  const link = <p className="ig-link"><a href={tagUrl} target="_blank" rel="noopener noreferrer">인스타그램에서 #{data.hashtag} 보기<span className="sr-only">(새 창)</span></a></p>;
  const shared = data.shared_with.length > 0 ? ` 다른 상권 ${data.shared_with.length}곳과 같은 해시태그를 써서 같은 값이 보여요.` : "";
  const head = <h3>인스타그램<small>#{data.hashtag} · 공식 API</small></h3>;

  if (data.status !== "collected") {
    return (
      <section className="panel ig-panel" aria-label="인스타그램">
        {head}
        <p className="pnote">{instagramPendingReason(data)}{shared}</p>
        {link}
      </section>
    );
  }

  const date = data.collected_at?.slice(0, 10) ?? null;
  const ageDays = data.collected_at ? (now - Date.parse(data.collected_at)) / DAY_MS : null;
  const stale = ageDays != null && data.stale_after_days != null && ageDays > data.stale_after_days;
  const mix = Object.entries(data.media_mix ?? {}).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${MEDIA_LABEL[k] ?? "기타"} ${Math.round(v * 100)}%`);
  const coTags = data.co_tags ?? [];
  const n = data.recent_24h ?? 0;
  return (
    <section className="panel ig-panel" aria-label="인스타그램">
      {head}
      <dl className="ig-facts">
        <dt>최근 24시간 게시물<small> 수집 시점 기준</small></dt>
        <dd><b className="num">{n.toLocaleString("ko-KR")}건{data.recent_capped ? " 이상" : ""}</b></dd>
        <dt>인기 게시물 반응<small> 중앙값 · 기간 무관</small></dt>
        <dd>
          좋아요 {data.top_likes_median != null ? data.top_likes_median.toLocaleString("ko-KR") : "—"} ·
          댓글 {data.top_comments_median != null ? data.top_comments_median.toLocaleString("ko-KR") : "—"}
          <small> 인기 게시물 {data.top_n ?? 0}건{data.top_likes_hidden ? ` · 좋아요를 숨긴 ${data.top_likes_hidden}건 제외` : ""}</small>
        </dd>
        {mix.length > 0 && <><dt>최근 24시간 게시물 형식</dt><dd>{mix.join(" · ")}</dd></>}
      </dl>
      {coTags.length > 0 && (
        <p className="ig-cotags" aria-label="함께 쓰인 해시태그">
          {coTags.map((t) => <span key={t.tag}>#{t.tag}<i>{t.n}</i></span>)}
        </p>
      )}
      <p className="pnote">
        수집 {date ?? "날짜 미상"}{stale ? " · 30일이 지난 값이에요" : ""}{data.refresh_error != null ? " · 최근 다시 받기에 실패해 지난 값이에요" : ""} ·
        {" "}게시물 수와 형식은 수집 시점의 {data.window} 표본이에요(공식 API 는 해시태그의 전체 게시물 수를 주지 않아요).
        인기 게시물은 기간과 상관없이 인스타그램이 고른 게시물이고, 함께 쓰인 태그는 두 목록에서 서로 다른 게시물 5건 이상만 보여요.
        계정·본문은 저장하지 않아요.{shared}
      </p>
      <p className="pnote">출처: {data.source}{data.api_version ? ` · ${data.api_version}` : ""}</p>
      {link}
    </section>
  );
}
