/**
 * 상권 흐름 — 파주 → 고양 → 서울(2026-10-26 사용자 요청).
 *
 * 「창업을 하는 경우 각 지역에서 고객들이 어떻게 이동할지, 서로 어떻게 연결이 될 수 있고 각 지역마다 어떻게 시너지를
 * 만들 수 있는지」를 한 화면의 흐름으로 읽는다. 화면이 말하는 것은 셋이다:
 *   ① 세 지역 사이 하루 이동 ② 마디(파주·고양은 시군구, 서울은 상권)마다 손님이 어디서·언제·무엇 하러 오는가
 *   ③ 측정으로 고른 짝(시너지 후보) — 「이 지역 사람이 하루 N명 저 상권으로 간다」까지가 측정이고,
 *      그 짝으로 무엇을 해 볼지는 **가설**로 적는다. 매출·성공을 약속하지 않는다.
 * 원천은 서울시×KT 수도권 생활이동 — 출발→도착 **집계**다. 「동선」이라 쓰지 않는다(docs/finding-movement-viz-2026-09-17.md).
 * ⛔ PPPP 네 화면을 대신하지 않는다 — 흐름에 더하는 화면이다(PPPP 화면 보존 규칙).
 */
import { useState } from "react";
import type { Corridor as CorridorData, CorridorNode, CorridorPair, CorridorSynergy, DistrictSummary } from "@/lib/api";
import { useFlow } from "../context";
import { httpStatus, useFlowData, useLoad } from "../data";
import { people, ro } from "../format";
import { comparePath, go } from "../route";
import { setDistrict } from "../state";
import {
  Badge, CloseButton, Details, FlowScreen, LoadError, ResultView, Row, RowList, Sheet, SkeletonRows, TextButton,
} from "../ui";
import { hasRanking, industryOf, useDistricts, useIndustries } from "./common";

const GROUP_LABEL: Record<string, string> = { work: "출근·등교", home: "귀가", visit: "방문(기타 포함)" };

/** 시각 목록 → 「18시·8시」 */
const hours = (hs: number[] | null | undefined, n = 2) => (hs ?? []).slice(0, n).map((h) => `${h}시`).join("·");

/** 구성비 → 「귀가 36% · 방문(기타 포함) 50%」 — 큰 것부터 */
function shares(m: Record<string, number> | null | undefined, label: (k: string) => string): string {
  if (!m) return "자료 없음";
  return Object.entries(m).filter(([, v]) => v >= 1).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${label(k)} ${Math.round(v)}%`).join(" · ");
}

/** 24시간 도착 막대 — 장식이 아니라 값이다(가장 많이 닿는 시각을 진하게). 읽기용 요약을 함께 단다 */
function HourBars({ share, peaks }: { share: number[]; peaks: number[] }) {
  const max = Math.max(...share, 0.0001);
  return (
    <figure className="fl-cor-hours" aria-label={`도착이 많은 시각 ${hours(peaks, 3)}`}>
      <div className="fl-cor-bars" aria-hidden="true">
        {share.map((v, h) => (
          <span key={h} className={peaks.slice(0, 2).includes(h) ? "is-peak" : undefined} style={{ height: `${Math.max(4, (v / max) * 100)}%` }} />
        ))}
      </div>
      <figcaption className="fl-cor-axis" aria-hidden="true"><span>0시</span><span>6시</span><span>12시</span><span>18시</span><span>23시</span></figcaption>
    </figure>
  );
}

/** 마디의 1층 월세 — 거점 값의 평균(만원/평). 없으면 null */
function nodeRent(n: CorridorNode | undefined): number | null {
  const v = (n?.hubs ?? []).map((h) => h.rent_1f_per_pyeong).filter((x): x is number => x != null);
  return v.length ? Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 10) / 10 : null;
}

/** 마디 월세에 빌려 쓴 통계가 얼마나 들었나 — 월세가 있는 상권 전부면 "all", 일부면 "some" */
function borrowedRent(n: CorridorNode): "all" | "some" | null {
  const rated = n.hubs.filter((h) => h.rent_1f_per_pyeong != null);
  const shared = rated.filter((h) => h.rent_shared).length;
  return !shared ? null : shared === rated.length ? "all" : "some";
}

function Synergy({ s, byId, onCompare, onValidate }: {
  s: CorridorSynergy; byId: Map<string, CorridorNode>;
  onCompare: (ids: string[]) => void; onValidate: (seoulHub: string) => void;
}) {
  const g = byId.get(s.node);
  const other = byId.get(s.from === s.node ? s.to : s.from);
  if (!g || !other) return null;
  const gHub = g.hubs[0]?.id;
  const oHub = other.hubs[0]?.id;
  const gRent = nodeRent(g);
  const oRent = nodeRent(other);
  // 빌려 쓴 임대 통계(rone-shared)가 든 마디는 비교 문장에서도 밝힌다 — 마디 상세의 「*」만으로는 카드에서 안 보인다
  const borrowed = [g, other].map((n) => {
    const b = borrowedRent(n);
    return b === "all" ? ` ${n.name} 값은 가까운 상권의 임대료 통계를 빌린 값이에요.`
      : b === "some" ? ` ${n.name} 값에는 빌린 임대료 통계가 섞여 있어요.` : "";
  }).join("");
  const rentLine = gRent != null && oRent != null && oRent > 0
    ? `${g.name} 1층 월세는 평당 ${gRent}만원으로 ${other.name}(${oRent}만원)의 약 ${Math.round((gRent / oRent) * 100)}%예요.${borrowed}`
    : null;
  // 짝의 시각·평균 분은 **모든 목적 합**(출근·귀가 포함)이다 — 방문 카드에 붙이면 방문 인원 옆에 귀가 시각이 서서
  // 방문 손님의 때로 읽힌다(10-27 검증: 망원→파주시 카드 19·18시, 방문만은 중앙 14시 무렵). 방문만의 시각이 산출물에
  // 서기 전까지 방문·유입 카드에는 시각을 붙이지 않고, 모든 목적을 세는 생활권 카드에만 붙인다.
  const when = `많이 닿는 때 ${hours(s.peak_hours) || "자료 없음"}${s.avg_min != null ? ` · 평균 ${Math.round(s.avg_min)}분` : ""}`;
  let title: string;
  let fact: string;
  let idea: string;
  switch (s.kind) {
    case "visit_link":
      title = `${g.name} 사람들이 방문하러 많이 가는 서울 상권 — ${other.name}`;
      fact = `방문하러 가는 사람 하루 ${people(s.visit_per_day)}`;
      idea = `${other.name}에서 팝업으로 반응을 먼저 보고, 같은 손님이 사는 ${g.name} 쪽에 자리를 잡는 길을 생각해 볼 수 있어요.`;
      break;
    case "inbound":
      title = `${other.name}에서 ${ro(g.name)} 방문하러 오는 사람`;
      fact = `하루 ${people(s.visit_per_day)}`;
      idea = `서울에서 일부러 찾아오는 흐름이 있어요 — ${other.name} 쪽 사람들에게 ${g.name} 가게를 알리는 방법을 작게 시험해 볼 수 있어요.`;
      break;
    default:
      title = `${g.name} ↔ ${other.name}, 한 생활권`;
      fact = `양쪽 합쳐 하루 ${people(s.per_day_both ?? s.per_day)} 오가요 · ${when}`;
      idea = "두 곳을 따로 보지 말고 한 생활권으로 나란히 견줘 볼 수 있어요.";
  }
  const seoulHub = other.segment === "seoul" ? oHub : null;
  return (
    <li className="fl-cor-syn">
      <h3>{title}</h3>
      <p className="fl-cor-fact">{fact}</p>
      <p className="fl-cor-idea"><Badge tone="est">가설</Badge> {idea}</p>
      {rentLine && <p className="fl-cor-fact">{rentLine}</p>}
      <div className="fl-actions">
        {gHub && oHub && <TextButton onClick={() => onCompare([gHub, oHub])}>두 상권 나란히 보기</TextButton>}
        {seoulHub && s.kind === "visit_link" && <TextButton onClick={() => onValidate(seoulHub)}>{other.name}에서 작게 확인하기</TextButton>}
      </div>
    </li>
  );
}

function NodeSheet({ node, byId, districts, industryOn, onClose }: {
  node: CorridorNode | null; byId: Map<string, CorridorNode>; districts: Map<string, DistrictSummary>;
  industryOn: boolean; onClose: () => void;
}) {
  if (!node) return <Sheet open={false} onClose={onClose} title="">{null}</Sheet>;
  const segName = (k: string) => ({ paju: "파주", goyang: "고양", seoul: "서울" } as Record<string, string>)[k] ?? k;
  const sourceLabel = (k: string) => k === "same_dong" ? "같은 동네"
    : k === "same_segment" ? (node.segment === "seoul" ? "서울 다른 동네" : `${segName(node.segment)} 안 다른 곳`)
      : k === "outer" ? "그 밖" : segName(k);
  const flows: CorridorPair[] = (node.segment === "seoul" ? node.top_origins : node.top_destinations) ?? [];
  return (
    <Sheet open onClose={onClose} title={node.name}>
      <dl className="fl-facts-list">
        <div><dt>어디서 오나요</dt><dd>{shares(node.inflow_share, sourceLabel)}</dd></div>
        <div><dt>무엇 하러 오나요</dt><dd>{shares(node.purpose_group_share, (k) => GROUP_LABEL[k] ?? k)}
          <span className="fl-dd-sub">「기타」에 비업무 방문 대부분이 들어가요 — 쇼핑으로 바꿔 부르지 않아요.</span></dd></div>
        <div><dt>언제 닿나요</dt><dd>{node.arr_hour_share && node.peak_hours
          ? <><b>{hours(node.peak_hours, 3)}</b><HourBars share={node.arr_hour_share} peaks={node.peak_hours} /></>
          : "자료 없음"}</dd></div>
        <div><dt>{node.segment === "seoul" ? "파주·고양에서 오는 곳" : "이 지역 사람이 많이 가는 곳"}</dt><dd>{flows.length
          ? flows.slice(0, 4).map((p) => {
            const other = byId.get(node.segment === "seoul" ? p.from : p.to);
            return <span key={`${p.from}|${p.to}`} className="fl-dd-sub">{other?.name ?? "?"} · 하루 {people(p.per_day)} · {hours(p.peak_hours)}</span>;
          }) : "자료 없음"}</dd></div>
      </dl>
      <h3 className="fl-h2">이 마디의 상권</h3>
      <RowList label={`${node.name} 상권`}>
        {node.hubs.map((h) => {
          const d = districts.get(h.id);
          return (
            <Row key={h.id} title={h.name}
              meta={[d?.vacancy_rate != null ? `공실률 ${d.vacancy_rate}%` : null,
                h.rent_1f_per_pyeong != null ? `1층 평당 ${h.rent_1f_per_pyeong}만원${h.rent_shared ? "*" : ""}` : "월세 통계 없음",
                industryOn && h.fit_rank != null ? `입지 점수 ${h.rank_group_name ? `${h.rank_group_name} ` : ""}${h.fit_rank}위` : null].filter(Boolean).join(" · ")}
              onClick={() => go(`/district/${encodeURIComponent(h.id)}`)} />
          );
        })}
      </RowList>
      <p className="fl-note">{node.kind === "sgg"
        ? "파주·고양은 이동 자료가 시군구 단위로만 있어요 — 같은 시군구의 상권은 같은 흐름 값을 써요."
        : "서울 상권 값은 상권이 걸친 행정동 기준이라 상권 손님 수보다 넓어요."}</p>
      {node.hubs.some((h) => h.rent_shared) && <p className="fl-note">* 가까운 상권의 임대료 통계를 빌려 쓴 값이에요.</p>}
    </Sheet>
  );
}

export function Corridor({ id }: { id: string }) {
  const { state, update } = useFlow();
  const data = useFlowData();
  const list = useIndustries();
  const ds = useDistricts();
  const ind = industryOf(state.industryKey, state.customIndustry, list.status === "ready" ? list.data : null);
  const industry = hasRanking(ind) ? ind!.key : null;
  const cor = useLoad(list.status === "loading" ? null : `cor:${id}:${industry ?? ""}`, () => data.corridor(id, industry));
  const [open, setOpen] = useState<string | null>(null);
  const caption = "상권 흐름";
  if (list.status === "loading" || cor.status === "loading") {
    return <FlowScreen back="/home" right={<CloseButton />} caption={caption} title="사람들이 오가는 흐름을 모으고 있어요">
      <SkeletonRows n={6} label="상권 흐름을 불러오는 중" /></FlowScreen>;
  }
  if (cor.status === "error") {
    if (httpStatus(cor.error) === 404) {
      return <FlowScreen back="/home" right={<CloseButton />} caption={caption} title="흐름 자료가 아직 없어요">
        <ResultView title="이 흐름은 아직 준비 중이에요" body="상권은 따로 골라 볼 수 있어요." action={{ label: "상권 고르기", onClick: () => go("/district-search") }} />
      </FlowScreen>;
    }
    return <FlowScreen back="/home" right={<CloseButton />} caption={caption} title="흐름을 불러오지 못했어요">
      <LoadError what="상권 흐름" error={cor.error} onRetry={cor.retry} />
    </FlowScreen>;
  }
  const c: CorridorData = cor.data;
  const byId = new Map(c.nodes.map((n) => [n.id, n]));
  const districts = new Map<string, DistrictSummary>((ds.status === "ready" ? ds.data : []).map((d) => [d.id, d]));
  const segName = new Map(c.segments.map((s) => [s.key, s.name]));
  const focus = state.districtId ? c.hub_nodes[state.districtId] ?? null : null;
  const cross = c.links.filter((l) => l.from !== l.to);
  const days = `${c.period.days[0]?.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3")} ~ ${c.period.days[c.period.days.length - 1]?.replace(/(\d{4})(\d{2})(\d{2})/, "$2-$3")}`;
  // 시너지 후보 — 지금 보는 상권의 마디가 경기면 그 마디 것부터, 아니면 경기 마디 순서대로.
  // 출근 짝(commute)은 카드로 내지 않는다 — 손님을 낮 동안 동네 밖으로 데려가는 흐름이라 창업자가 기댈 연결이
  // 아니고, 10-26 실측에서 네 마디 모두 같은 서울 상권(을지로)을 가리켰다. 출근은 마디 상세의 목적 구성·시각 막대가 보여 준다.
  const gyeonggiNodes = c.nodes.filter((n) => n.segment !== "seoul");
  const order = focus && gyeonggiNodes.some((n) => n.id === focus)
    ? [focus, ...gyeonggiNodes.map((n) => n.id).filter((x) => x !== focus)] : gyeonggiNodes.map((n) => n.id);
  const synergies = order.flatMap((nid) => c.synergies.filter((s) => s.node === nid && s.kind !== "commute"));
  const compare = (ids: string[]) => go(comparePath(ids));
  const validate = (hub: string) => { update((s) => setDistrict(s, hub)); go("/validate"); };
  return (
    <FlowScreen wide back="/home" right={<CloseButton />} caption={caption}
      title="파주 → 고양 → 서울, 사람들이 이렇게 오가요"
      sub={`출발→도착 집계예요(한 사람의 동선이 아니에요) · ${days} 하루 평균(평일 ${c.period.weekday}일·주말 ${c.period.weekend}일)`}>
      <h2 className="fl-h2">세 지역 사이 하루 이동</h2>
      <RowList label="지역 사이 하루 이동">
        {cross.map((l) => (
          <Row key={`${l.from}|${l.to}`} title={`${segName.get(l.from) ?? l.from} → ${segName.get(l.to) ?? l.to}`}
            meta={`많이 닿는 때 ${hours(l.peak_hours)}${l.avg_min != null ? ` · 평균 ${Math.round(l.avg_min)}분` : ""}`}
            right={<><b>{people(l.per_day)}</b><span>하루</span></>} />
        ))}
      </RowList>

      {c.segments.map((seg) => {
        const nodes = c.nodes.filter((n) => n.segment === seg.key && n.on_corridor)
          .sort((a, b) => (a.corridor_rank ?? 0) - (b.corridor_rank ?? 0));
        if (!nodes.length) return null;
        return (
          <section key={seg.key} aria-label={seg.name}>
            <h2 className="fl-h2">{seg.name}</h2>
            {seg.key === "seoul" && <p className="fl-note">파주·고양 사람이 많이 오는 서울 상권 {nodes.length}곳이에요.</p>}
            <RowList label={`${seg.name} 마디`}>
              {nodes.map((n) => (
                <Row key={n.id} pinned={n.id === focus} rank={n.corridor_rank ?? undefined}
                  title={<>{n.name} <Badge tone="obs">{n.role.kind}</Badge></>}
                  meta={n.segment === "seoul" ? `파주·고양에서 하루 ${people(n.from_gyeonggi_per_day)}`
                    : `상권 ${n.hubs.map((h) => h.name).join("·") || "없음"}`}
                  right={<span>많이 닿는 때 {hours(n.peak_hours) || "—"}</span>}
                  onClick={() => setOpen(n.id)} />
              ))}
            </RowList>
          </section>
        );
      })}

      <h2 className="fl-h2">이렇게 이어 볼 수 있어요</h2>
      <p className="fl-note">이동 수까지가 측정이에요. 「이렇게 해 볼 수 있다」는 가설이라 매출이나 성공을 약속하지 않아요 — 작게 먼저 확인해 보세요.</p>
      <ul className="fl-cor-syns" aria-label="시너지 후보">
        {synergies.map((s) => <Synergy key={`${s.kind}|${s.node}|${s.from}|${s.to}`} s={s} byId={byId} onCompare={compare} onValidate={validate} />)}
      </ul>

      <Details summary="자료와 한계">
        <ul className="fl-facts">{c.caveats.map((t) => <li key={t}>{t}</li>)}</ul>
        <p className="fl-note">역할(출근형·주거형·방문형)은 도착 목적 구성이 흐름 안 중앙값보다 {c.params.role_margin_pp ?? 3}%p 이상 높은 쪽이에요. 넘는 것이 없으면 혼합이에요.</p>
        {industry && (c.rank_groups?.length ?? 0) > 1 && <p className="fl-note">입지 점수 순위는 {c.rank_groups!.map((g) => g.name).join(" · ")} 묶음마다 다른 모델로 따로 매겼어요 — 묶음이 다른 상권끼리는 견주지 않아요.</p>}
        <p className="fl-note mono">{c.source}</p>
      </Details>

      <NodeSheet node={open ? byId.get(open) ?? null : null} byId={byId} districts={districts} industryOn={!!industry} onClose={() => setOpen(null)} />
    </FlowScreen>
  );
}
