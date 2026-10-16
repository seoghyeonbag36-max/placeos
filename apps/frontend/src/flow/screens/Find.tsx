/**
 * ① 상권 찾기(PLATFORM) — 화면설계서 5판 §5-1: Q1 목적 · Q2 업종 · Q2-1 직접 적기 · Q3 지금 상권 ·
 * R1 상권 순위 · R1-p 업종 순위(바꾸기) · Q-p 무엇부터 · Q4 상권 직접 고르기 · R2 상권 소개.
 */
import { useEffect, useState } from "react";
import type { BusinessGoal } from "@/lib/businessProfile";
import type { DistrictSummary, IndustryFitRow } from "@/lib/api";
import { useFlow } from "../context";
import { httpStatus, useFlowData, useLoad } from "../data";
import { eun, iga, ro } from "../format";
import { go } from "../route";
import { setDistrict, setGoal, setHomeDistrict, setIndustry } from "../state";
import {
  Badge, BottomCTA, ChoiceList, CloseButton, Details, FlowScreen, LoadError, ResultView, Row, RowList, Sheet,
  SkeletonRows, TextButton, WarnLine,
} from "../ui";
import {
  GOAL_LABEL, INDUSTRY_EMOJI, districtById, hasRanking, industryOf, matches, useDistrictName, useDistricts,
  useIndustries, useNeed,
} from "./common";

/* ── Q1 목적 ─────────────────────────────────────────────────────────────── */

const GOALS: { value: BusinessGoal; title: string; desc: string }[] = [
  { value: "start", title: "새 가게를 열어요", desc: "업종은 정했고, 어느 동네가 좋을지 찾고 있어요" },
  { value: "pivot", title: "지금 가게 업종을 바꿔요", desc: "자리는 그대로, 무엇으로 바꿀지 고민이에요" },
  { value: "move", title: "하던 장사를 다른 동네로 옮겨요", desc: "같은 업종으로 옮길 상권을 찾고 있어요" },
];

export function Start() {
  const { state, update, token, openLogin } = useFlow();
  return (
    <FlowScreen back={null}
      right={token ? <CloseButton /> : <button type="button" className="fl-textbtn" onClick={openLogin}>로그인</button>}
      title="어떤 준비를 하고 계세요?" sub="고른 목적에 맞춰 상권을 보여 드려요.">
      <ChoiceList label="준비하는 일" value={state.goal} options={GOALS}
        onChoose={(g) => { update((s) => setGoal(s, g)); go("/industry"); }} />
      <p className="fl-foot">로그인 없이 끝까지 볼 수 있어요. 저장할 때만 로그인해요.</p>
    </FlowScreen>
  );
}

/* ── Q2 업종 ─────────────────────────────────────────────────────────────── */

const INDUSTRY_Q: Record<BusinessGoal, string> = {
  start: "어떤 가게를 여시나요?", move: "어떤 가게를 하고 계세요?", pivot: "지금은 어떤 가게인가요?",
};

export function Industry() {
  const { state, update } = useFlow();
  const data = useFlowData();
  const list = useIndustries();
  const ok = useNeed(!!state.goal, "/start");
  if (!ok || !state.goal) return null;
  const goal = state.goal;
  const next = (key: string) => {
    if (key === "other") { go("/industry/other"); return; }
    update((s) => setIndustry(s, key));
    if (goal === "start") {
      // 미리 받기 — R1 이 열릴 때 이미 와 있게(No More Loading)
      if (list.status === "ready" && hasRanking(list.data.find((o) => o.key === key))) {
        data.prefetch(() => data.industryFit(key));
      }
      data.prefetch(data.districts);
      go("/districts");
    } else {
      data.prefetch(data.districts);
      go("/home-district");
    }
  };
  return (
    <FlowScreen back="/start" caption={`상권 찾기 · ${GOAL_LABEL[goal]}`} title={INDUSTRY_Q[goal]}
      sub={goal === "pivot" ? "지금 업종을 기준으로 이 상권에 맞는 업종을 견줘 드려요." : "업종에 맞는 상권부터 보여 드려요."}>
      {list.status === "loading" && <SkeletonRows n={4} label="업종 목록을 불러오는 중" />}
      {list.status === "error" && <LoadError what="업종 목록" error={list.error} onRetry={list.retry}
        other={{ label: "상권부터 고르기", onClick: () => go("/district-search") }} />}
      {list.status === "ready" && (
        <ChoiceList tiles label="업종" value={state.industryKey} onChoose={next}
          options={[...list.data.map((o) => ({
            value: o.key,
            title: <><span className="fl-tile-emoji" aria-hidden="true">{INDUSTRY_EMOJI[o.key] ?? "🏬"}</span>{o.label}</>,
            desc: goal !== "pivot" && !hasRanking(o) ? "상권은 직접 골라요" : undefined,
          })), { value: "other", title: <><span className="fl-tile-emoji" aria-hidden="true">✏️</span>기타 · 직접 적기</> }]} />
      )}
    </FlowScreen>
  );
}

/* ── Q2-1 업종 직접 적기 ──────────────────────────────────────────────────── */

export function IndustryOther() {
  const { state, update } = useFlow();
  const [text, setText] = useState(state.industryKey === "other" ? state.customIndustry ?? "" : "");
  const ok = useNeed(!!state.goal, "/start");
  if (!ok || !state.goal) return null;
  const goal = state.goal;
  const value = text.trim();
  const submit = () => {
    if (!value) return;
    update((s) => setIndustry(s, "other", value.slice(0, 120)));
    go(goal === "start" ? "/districts" : "/home-district");
  };
  return (
    <FlowScreen back="/industry" caption={`상권 찾기 · ${GOAL_LABEL[goal]}`} title="어떤 가게인지 적어 주세요"
      sub="적은 업종은 순위·본전 계산 없이 빈 자리와 월세까지 볼 수 있어요."
      cta={<BottomCTA primary={{ label: "다음", onClick: submit, disabled: !value }} />}>
      <label className="fl-textfield">
        <span className="sr-only">업종</span>
        <input autoFocus maxLength={120} value={text} placeholder="예: 도자기 공방" onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } }} />
      </label>
    </FlowScreen>
  );
}

/* ── 상권 고르기 목록 — Q3 · Q4 가 같이 쓴다 ─────────────────────────────── */

function DistrictPickList({ onPick, emptyHint }: { onPick: (d: DistrictSummary) => void; emptyHint: string }) {
  const ds = useDistricts();
  const [q, setQ] = useState("");
  if (ds.status === "loading") return <SkeletonRows n={6} label="상권 목록을 불러오는 중" />;
  if (ds.status === "error") return <LoadError what="상권 목록" error={ds.error} onRetry={ds.retry} />;
  const shown = ds.data.filter((d) => matches(d, q)).sort((a, b) => a.name.localeCompare(b.name, "ko"));
  return (
    <>
      <label className="fl-search">
        <span className="sr-only">동네 이름으로 찾기</span>
        <input type="search" value={q} placeholder="동네 이름으로 찾기" onChange={(e) => setQ(e.target.value)} />
      </label>
      {shown.length === 0 ? (
        <p className="fl-empty">찾는 상권이 없어요. 지금은 서울 {ds.data.length}개 상권만 있어요 — {emptyHint}</p>
      ) : (
        <RowList label="상권">
          {shown.map((d) => (
            <Row key={d.id} title={<>{d.name}{d.caveat ? <span className="fl-caveat-mark" title={d.caveat}> ▣</span> : null}</>}
              meta={`${d.gu}${d.vacancy_rate != null ? ` · 공실률 ${d.vacancy_rate}%` : ""}`} onClick={() => onPick(d)} />
          ))}
        </RowList>
      )}
    </>
  );
}

/* ── Q3 지금 가게 상권(바꾸기·옮기기) ─────────────────────────────────────── */

export function HomeDistrict() {
  const { state, update } = useFlow();
  const data = useFlowData();
  const list = useIndustries();
  const ok = useNeed(!!state.goal && state.goal !== "start" && !!state.industryKey, state.goal ? "/industry" : "/start");
  if (!ok) return null;
  const ind = industryOf(state.industryKey, state.customIndustry, list.status === "ready" ? list.data : null);
  return (
    <FlowScreen back="/industry" caption={`상권 찾기 · ${ind?.label ?? GOAL_LABEL[state.goal!]}`} title="지금 가게는 어느 상권에 있나요?">
      <DistrictPickList emptyHint="가까운 상권을 골라 주세요." onPick={(d) => {
        update((s) => setHomeDistrict(s, d.id));
        if (state.goal === "pivot") {
          data.prefetch(() => data.districtIndustries(d.id));
          go("/industries");
        } else {
          if (hasRanking(ind)) data.prefetch(() => data.industryFit(state.industryKey!));
          go("/districts");
        }
      }} />
    </FlowScreen>
  );
}

/* ── R1 상권 순위 ────────────────────────────────────────────────────────── */

/** 순위 한 줄 — 오른쪽 빈 1층 수는 그 상권 층 산출물에서 센다(상위 5곳만 요청) */
function RankLine({ row, onPick, pinned, rankLabel }: { row: IndustryFitRow; onPick: () => void; pinned?: boolean; rankLabel?: string }) {
  const data = useFlowData();
  const floors = useLoad(`fs:${row.district_id}`, () => data.floorSummary(row.district_id));
  const vacant1f = floors.status === "ready" ? floors.data.by_floor["1"] ?? 0 : null;
  return (
    <Row pinned={pinned} rank={rankLabel ?? row.fit_rank ?? "–"} onClick={onPick}
      title={row.name ?? row.district_id} meta={row.gu ?? undefined}
      right={<>
        <b>{floors.status === "loading" ? "빈 1층 …" : floors.status === "error" ? (httpStatus(floors.error) === 404 ? "층 자료 없음" : "빈 1층 ?") : `빈 1층 ${vacant1f}곳`}</b>
        <span>{row.rent_1f_per_pyeong != null ? `1층 평당 ${row.rent_1f_per_pyeong}만원${row.rent_shared ? "*" : ""}` : "월세 통계 없음"}</span>
      </>} />
  );
}

export function Districts() {
  const { state, update } = useFlow();
  const data = useFlowData();
  const list = useIndustries();
  const ok = useNeed(!!state.goal && !!state.industryKey && (state.goal === "start" || !!state.homeDistrictId),
    !state.goal ? "/start" : !state.industryKey ? "/industry" : "/home-district");
  const ind = industryOf(state.industryKey, state.customIndustry, list.status === "ready" ? list.data : null);
  const ranked = hasRanking(ind);
  const fit = useLoad(ok && ranked && ind ? `fit:${ind.key}` : null, () => data.industryFit(ind!.key));
  const [why, setWhy] = useState(false);
  if (!ok) return null;
  const caption = `상권 찾기 · ${ind?.label ?? "…"}`;
  const pick = (id: string) => {
    update((s) => setDistrict(s, id));
    data.prefetch(() => data.platform(id), () => data.rent(id), () => data.floorSummary(id));
    go(`/district/${encodeURIComponent(id)}`);
  };
  if (list.status === "loading" || (ranked && fit.status === "loading")) {
    return <FlowScreen back={state.goal === "start" ? "/industry" : "/home-district"} right={<CloseButton />} caption={caption}
      title="상권 순위를 세고 있어요"><SkeletonRows n={5} label="상권 순위를 불러오는 중" /></FlowScreen>;
  }
  if (list.status === "error") {
    return <FlowScreen back="/industry" caption={caption} title="업종 정보를 불러오지 못했어요">
      <LoadError what="업종 목록" error={list.error} onRetry={list.retry} />
    </FlowScreen>;
  }
  // 모델 밖 업종 — 같은 주소, 다른 결론(가까운 업종 점수로 채우지 않는다)
  if (!ranked || (fit.status === "ready" && (!fit.data.model_covered || fit.data.ranked_n === 0))) {
    return (
      <FlowScreen back={state.goal === "start" ? "/industry" : "/home-district"} right={<CloseButton />} caption={caption}
        title={ind ? `${eun(ind.label)} 상권 순위를 아직 못 드려요` : "상권 순위를 아직 못 드려요"}
        sub="상권을 직접 고르면 빈 자리와 월세는 볼 수 있어요."
        cta={<BottomCTA primary={{ label: "상권 직접 고르기", onClick: () => go("/district-search") }} />}>
        <p className="fl-note">{(fit.status === "ready" ? fit.data.fit_unavailable_reason : null)
          ?? ind?.fit_unavailable_reason ?? "이 업종의 상권 순위를 계산할 자료가 아직 없어요."}</p>
      </FlowScreen>
    );
  }
  if (fit.status === "error") {
    return <FlowScreen back="/industry" right={<CloseButton />} caption={caption} title="상권 순위를 불러오지 못했어요">
      <LoadError what="상권 순위" error={fit.error} onRetry={fit.retry} other={{ label: "상권 직접 고르기", onClick: () => go("/district-search") }} />
    </FlowScreen>;
  }
  if (fit.status !== "ready" || !ind) return null;
  const rows = fit.data.districts.filter((r) => r.fit_rank != null).sort((a, b) => a.fit_rank! - b.fit_rank!);
  const top = rows.slice(0, 5);
  const home = state.goal === "move" ? rows.find((r) => r.district_id === state.homeDistrictId) : undefined;
  const homeInTop = !!home && top.some((r) => r.district_id === home.district_id);
  const diff = home && top[0] && home.fit != null && top[0].fit != null ? Math.round((top[0].fit - home.fit) * 100) : null;
  return (
    <FlowScreen wide back={state.goal === "start" ? "/industry" : "/home-district"} right={<CloseButton />} caption={caption}
      title={`${ind.label} 입지 점수가 높은 상권이에요`}
      sub={`비슷한 자리에 ${iga(ind.label)} 얼마나 들어서 있는지로 매긴 순위예요. 매출 순위는 아니에요.`}>
      <RowList label={`${ind.label} 상권 순위`}>
        {home && !homeInTop && (
          <RankLine row={home} pinned rankLabel={`${home.fit_rank}`} onPick={() => pick(home.district_id)} />
        )}
        {top.map((r) => <RankLine key={r.district_id} row={r} onPick={() => pick(r.district_id)} />)}
      </RowList>
      {home && (
        <p className="fl-note">{homeInTop ? `지금 내 상권 ${home.name}은 ${home.fit_rank}위예요.`
          : `지금 내 상권 ${home.name}은 ${home.fit_rank}위예요${diff != null && diff > 0 ? ` — 1위보다 ${diff}점 낮아요` : ""}.`}</p>
      )}
      {rows.some((r) => r.rent_shared) && <p className="fl-note">* 가까운 상권의 임대료 통계를 빌려 쓴 값이에요.</p>}
      <div className="fl-actions">
        <TextButton onClick={() => setWhy(true)}>왜 이 순서인가요?</TextButton>
        <TextButton onClick={() => go("/district-search")}>다른 상권 직접 고르기</TextButton>
      </div>
      <Sheet open={why} onClose={() => setWhy(false)} title="왜 이 순서인가요?">
        <p>입지 점수는 비슷한 자리에 {ind.label} 가게가 이미 얼마나 모여 있는지를 추천 모델이 배운 값이에요(×100). 매출이나 생존율이 아니에요.</p>
        <ul className="fl-facts">
          {fit.data.seoul_fit != null && <li>서울 평균 입지 점수 {Math.round(fit.data.seoul_fit * 100)}점</li>}
          <li>순위를 매긴 상권 {fit.data.ranked_n}곳</li>
          {top[0]?.same_n != null && top[0]?.sample_n != null && <li>1위 상권 표본 {top[0].sample_n}곳 중 같은 업종 {top[0].same_n}곳</li>}
        </ul>
        <p className="fl-note">{fit.data.note}</p>
        <p className="fl-note mono">{fit.data.source}</p>
      </Sheet>
    </FlowScreen>
  );
}

/* ── R1-p 업종 순위(바꾸기) ───────────────────────────────────────────────── */

export function Industries() {
  const { state, update } = useFlow();
  const data = useFlowData();
  const list = useIndustries();
  const home = state.homeDistrictId;
  const ok = useNeed(state.goal === "pivot" && !!state.industryKey && !!home, state.goal === "pivot" ? "/home-district" : "/start");
  const rows = useLoad(ok && home ? `di:${home}` : null, () => data.districtIndustries(home!));
  const homeName = useDistrictName(home);
  if (!ok) return null;
  const now = industryOf(state.industryKey, state.customIndustry, list.status === "ready" ? list.data : null);
  const pickTarget = (key: string) => {
    update((s) => ({ ...s, targetIndustryKey: key }));
    go("/pivot-next");
  };
  const caption = `업종 바꾸기 · ${homeName ?? "지금 상권"}`;
  if (rows.status === "loading") return <FlowScreen back="/home-district" right={<CloseButton />} caption={caption} title="업종 순위를 세고 있어요"><SkeletonRows n={5} /></FlowScreen>;
  // 이 상권에 업종 순위가 없으면 — 같은 화면에서 업종을 직접 고른다(한 화면 한 질문)
  if (rows.status === "error") {
    if (httpStatus(rows.error) !== 404) return <FlowScreen back="/home-district" right={<CloseButton />} caption={caption} title="업종 순위를 불러오지 못했어요"><LoadError what="업종 순위" error={rows.error} onRetry={rows.retry} /></FlowScreen>;
    return (
      <FlowScreen back="/home-district" right={<CloseButton />} caption={caption} title="어떤 업종으로 바꿔 볼까요?"
        sub="이 상권은 업종 순위가 아직 없어요. 바꿔 볼 업종을 직접 골라 주세요.">
        {list.status === "ready" && <ChoiceList tiles label="바꿔 볼 업종" value={state.targetIndustryKey} onChoose={pickTarget}
          options={list.data.filter((o) => o.key !== state.industryKey).map((o) => ({
            value: o.key, title: <><span className="fl-tile-emoji" aria-hidden="true">{INDUSTRY_EMOJI[o.key] ?? "🏬"}</span>{o.label}</>,
          }))} />}
      </FlowScreen>
    );
  }
  const ranked = rows.data.rows.filter((r) => r.fit_rank != null).sort((a, b) => a.fit_rank! - b.fit_rank!);
  const unranked = rows.data.rows.filter((r) => r.fit_rank == null);
  const mine = rows.data.rows.find((r) => r.key === state.industryKey);
  return (
    <FlowScreen wide back="/home-district" right={<CloseButton />} caption={caption}
      title={`${homeName ? `${homeName}에서` : "이 상권에서"} 입지 점수가 높은 업종이에요`}
      sub={mine?.fit_rank != null && now ? `지금 업종 ${eun(now.label)} ${mine.fit_rank}위예요.` : "지금 업종은 순위를 내지 않는 업종이에요."}>
      <RowList label="업종 순위">
        {[...ranked, ...unranked].map((r) => {
          const isMine = r.key === state.industryKey;
          return (
            <Row key={r.key} pinned={isMine} current={isMine} rank={r.fit_rank ?? "–"}
              title={<>{r.label}{isMine && <> <Badge tone="primary">지금</Badge></>}</>}
              meta={r.same_share != null ? `${r.fit_rank == null ? "순위 없이 " : ""}같은 업종 ${Math.round(r.same_share * 100)}%` : undefined}
              onClick={isMine ? undefined : () => pickTarget(r.key)} />
          );
        })}
      </RowList>
      <Details><p className="fl-note">{rows.data.note}</p><p className="fl-note mono">{rows.data.source}</p></Details>
    </FlowScreen>
  );
}

/* ── Q-p 무엇부터(바꾸기) ─────────────────────────────────────────────────── */

export function PivotNext() {
  const { state, update } = useFlow();
  const list = useIndustries();
  const ok = useNeed(state.goal === "pivot" && !!state.targetIndustryKey && !!state.homeDistrictId, "/industries");
  if (!ok) return null;
  const target = industryOf(state.targetIndustryKey, null, list.status === "ready" ? list.data : null);
  const label = target?.label ?? "새 업종";
  return (
    <FlowScreen back="/industries" caption={`업종 바꾸기 · ${ro(label)}`} title={`${ro(label)} 바꾼다면, 무엇부터 해 볼까요?`}>
      <ChoiceList label="먼저 할 일" value={null} options={[
        { value: "validate", title: "작게 먼저 팔아 볼게요", desc: "팝업·가오픈·사전 예약으로 통하는지 확인해요" },
        { value: "spaces", title: "이 상권 빈 자리도 볼게요", desc: "옮겨서 하는 경우와 견줘 봐요" },
      ]} onChoose={(v) => {
        if (v === "validate") go("/validate");
        else { update((s) => setDistrict(s, s.homeDistrictId!)); go("/rent-cap"); }
      }} />
      <p className="fl-foot">지금 가게 자리로 본전을 계산하는 기능은 아직 없어요.</p>
    </FlowScreen>
  );
}

/* ── Q4 상권 직접 고르기 ──────────────────────────────────────────────────── */

export function DistrictSearch() {
  const { state, update } = useFlow();
  const data = useFlowData();
  const list = useIndustries();
  const ind = industryOf(state.industryKey, state.customIndustry, list.status === "ready" ? list.data : null);
  return (
    <FlowScreen back="/districts" right={<CloseButton />} caption={`상권 찾기${ind ? ` · ${ind.label}` : ""}`} title="어느 상권을 볼까요?">
      <DistrictPickList emptyHint="가까운 상권을 골라 주세요." onPick={(d) => {
        update((s) => setDistrict(s, d.id));
        data.prefetch(() => data.platform(d.id), () => data.rent(d.id), () => data.floorSummary(d.id));
        go(`/district/${encodeURIComponent(d.id)}`);
      }} />
    </FlowScreen>
  );
}

/* ── R2 상권 소개 ────────────────────────────────────────────────────────── */

/** archetype 「카페 중심형」 「음식·카페 복합형」 → 문장 속 말 */
const archetypePhrase = (a: string) => a.replace(/중심형$/, "중심").replace(/복합형$/, "복합");

export function District({ id }: { id: string }) {
  const { state, update } = useFlow();
  const data = useFlowData();
  const ds = useDistricts();
  const platform = useLoad(`plat:${id}`, () => data.platform(id));
  const rent = useLoad(`rent:${id}`, () => data.rent(id));
  const floors = useLoad(`fs:${id}`, () => data.floorSummary(id));
  // 주소로 바로 열었으면 보는 상권을 이 상권으로(뒤 답을 비우는 규칙은 setDistrict 가 지킨다)
  useEffect(() => { if (state.districtId !== id) update((s) => setDistrict(s, id)); }, [id, state.districtId, update]);
  const d = ds.status === "ready" ? districtById(ds.data, id) : null;
  if (ds.status === "ready" && !d) {
    return <FlowScreen back="/district-search" right={<CloseButton />} title="이 상권을 찾지 못했어요">
      <ResultView title="지금 서비스하는 상권이 아니에요" body="목록에서 다시 골라 주세요." action={{ label: "상권 고르기", onClick: () => go("/district-search") }} />
    </FlowScreen>;
  }
  const name = d?.name ?? "이 상권";
  const identity = platform.status === "ready" ? platform.data.identity : null;
  const groups = identity?.categories.groups ?? [];
  const demand = identity?.demand;
  const peak = demand?.bands?.find((b) => b.band === demand.peak_band)?.label;
  const quiet = demand?.bands?.find((b) => b.band === demand.gap_band)?.label;
  const title = identity?.archetype ? `${eun(name)} ${archetypePhrase(identity.archetype)} 상권이에요` : `${name}을 한눈에 볼게요`;
  const loading = platform.status === "loading" || rent.status === "loading" || floors.status === "loading" || ds.status === "loading";
  const next = () => {
    data.prefetch(() => data.rent(id), () => data.floorUnits(id), () => data.postings(id));
    go("/rent-cap");
  };
  return (
    <FlowScreen back="/districts" right={<CloseButton />} caption={`상권${d ? ` · ${d.gu}` : ""}`} title={loading ? `${name}을 살펴보고 있어요` : title}
      cta={<BottomCTA primary={{ label: "빈 자리 보기", onClick: next }} />}>
      {d?.caveat && <WarnLine>{d.caveat}</WarnLine>}
      {loading ? <SkeletonRows n={4} label="상권 소개를 불러오는 중" /> : (
        <dl className="fl-facts-list">
          <div><dt>무엇이 모여 있나요</dt><dd>{groups.length ? groups.slice(0, 2).map((g) => `${g.group} ${Math.round(g.share * 100)}%`).join(" · ") : "업종 구성 자료가 없어요"}</dd></div>
          <div><dt>언제 붐비나요</dt><dd>{peak ? `${peak}${quiet ? ` · 한산한 때 ${quiet}` : ""}` : "시간대 자료가 없어요"}</dd></div>
          <div><dt>1층 월세는</dt><dd>{rent.status === "ready"
            ? <>평당 {rent.data.base_rent_per_pyeong}만원 <Badge tone="est">추정</Badge>{rent.data.rent_source === "rone-shared" && <span className="fl-dd-sub">가까운 상권 통계를 빌렸어요</span>}</>
            : "이 상권은 임대료 통계가 없어요"}</dd></div>
          <div><dt>빈 자리는</dt><dd>{floors.status === "ready"
            ? <>빈 층 {floors.data.counts_all.units ?? floors.data.total}곳 · 1층 {floors.data.by_floor["1"] ?? 0} <Badge tone="real">대장 실측</Badge></>
            : "층 단위 자료가 아직 없어요"}</dd></div>
        </dl>
      )}
      <p className="fl-source">카카오 플레이스 · 서울시 상권분석{rent.status === "ready" && rent.data.quarter ? ` · R-ONE ${rent.data.quarter}` : " · R-ONE"} · 건축물대장</p>
      {identity?.archetype_rule && <Details><p className="fl-note">상권 유형은 이렇게 정했어요: {identity.archetype_rule}</p></Details>}
      <div className="fl-actions"><TextButton onClick={() => go("/explore")}>지도에서 자세히</TextButton></div>
    </FlowScreen>
  );
}
