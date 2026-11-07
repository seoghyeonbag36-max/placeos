import { useEffect, useId, useRef, useState } from "react";
import { generateInterior, getInteriorQuota, interiorErrorMessage, tierAvailable, type InteriorImage } from "@/lib/api";
import { EXTRA_MAX, INTERIOR_KEYWORD_GROUPS, MAX_KEYWORDS, composeStyle } from "@/lib/interiorKeywords";
import { loadToken } from "@/lib/session";
import type { ProgramHandoff } from "@/lib/workspaceState";
import "./InteriorPlanner.css";
import InteriorDesignControls from "./InteriorDesignControls";
import { defaultInteriorDesign, interiorDesignBrief } from "./interiorDesign";

type Strategy = "고급화" | "가성비" | "기능중심";
type Reference = { kind: "plan" | "photo"; mime: string; data: string; name: string };
/** 서버가 알려 준 오늘 생성 한도. 서버가 답하지 않으면 null — 그때는 막지 않고 서버의 판정(429)을 따른다. */
type Quota = { enabled: boolean; limit: number; remaining: number };
const STRATEGIES: [string, Strategy][] = [["premium", "고급화"], ["value", "가성비"], ["factory", "기능중심"]];
const CATEGORIES: [string, string][] = [["all", "전체"], ...INTERIOR_KEYWORD_GROUPS.map((g): [string, string] => [g.id, g.label])];

function download(name: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** 사용자 조건과 Posting 계산을 명시해 생성한다. 어울림 점수·내부 치수·시공 견적은 만들지 않는다. */
export default function InteriorPlanner({ handoff, district, industry }: {
  handoff?: ProgramHandoff; district?: string | null; industry?: string;
}) {
  // 분위기·색감 — 분류 필터로 키워드를 골라 쌓는다(2026-11-07). 직접 입력은 보조다.
  const [keywords, setKeywords] = useState<string[]>([]);
  const [category, setCategory] = useState("all");
  const [extra, setExtra] = useState("");
  const style = composeStyle(keywords, extra);
  const [design, setDesign] = useState(defaultInteriorDesign);
  const designBrief = interiorDesignBrief(design);
  const effectiveStyle = [style, design.concept].filter(Boolean).join(" · ");
  const [strategy, setStrategy] = useState<Strategy>(
    STRATEGIES.find(([, label]) => label === handoff?.strategy)?.[1] ?? "가성비");
  const [constraints, setConstraints] = useState("");
  const [links, setLinks] = useState("");
  const [references, setReferences] = useState<Reference[]>([]);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [result, setResult] = useState<{ image: InteriorImage; prompt: string } | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);
  const selectedDistrict = handoff?.districtName ?? handoff?.districtId ?? district ?? "";
  const selectedIndustry = handoff?.industry ?? industry ?? "";
  const [ownDistrict, setOwnDistrict] = useState(selectedDistrict);
  const [ownIndustry, setOwnIndustry] = useState(selectedIndustry);
  const scenarios = handoff?.calculation?.result.scenarios;
  const request = {
    district: ownDistrict, industry: ownIndustry, style: effectiveStyle, strategy,
    ...(handoff?.area ? { area_py: handoff.area } : {}),
    constraints: [constraints, designBrief].filter(Boolean).join("\n"), links: links.split("\n").map((s) => s.trim()).filter(Boolean),
    references: references.map(({ kind, mime, data }) => ({ kind, mime, data })), consent: true as const,
  };
  const brief = `AI 인테리어 참고안 · 실측 도면·시공안 아님\n상권: ${ownDistrict}\n업종: ${ownIndustry}\n자리: ${handoff?.unitName ?? "미선택"}\n면적: ${handoff?.area ?? "미확인"}평\n전략: ${strategy}\n분위기: ${style}\n보존할 구조·운영 제약: ${constraints || "미입력"}\n참고 링크(원문 미확인): ${links || "없음"}\n사용자 참고 이미지: ${references.map((r) => `${r.kind} ${r.name}`).join(", ") || "없음"}\n도면의 벽·기둥·출입구를 보존하고, 확인되지 않은 치수·수요·매출·법규 적합성을 주장하지 말 것.`;
  // 서버가 미설정이라고 답했거나 오늘 몫을 다 썼으면 생성을 부르지 않는다 — 지시문 저장은 그대로 열어 둔다.
  const blocked = quota !== null && (!quota.enabled || quota.remaining <= 0);
  // 생성 버튼이 잠긴 이유를 버튼 옆에 그대로 보인다(2026-11-07 「AI 이미지 생성칸이 안 눌린다」 제보) —
  // 잠긴 버튼만 보이면 고장으로 읽힌다. 이 목록이 비어야 버튼이 열린다(아래 disabled 와 같은 조건).
  const lockReasons = [
    ...(!ownDistrict.trim() ? ["상권을 입력하세요."] : []),
    ...(!ownIndustry.trim() ? ["디자인할 업종을 입력하세요."] : []),
    ...(!effectiveStyle.trim() ? ["분위기·색감 키워드나 인테리어 콘셉트를 하나 이상 고르세요."] : []),
    ...(!consent ? ["위의 외부 AI(OpenAI) 전송 동의에 체크하세요."] : []),
    ...(quota && !quota.enabled ? ["서버에서 이미지 생성이 꺼져 있습니다(운영자 설정 필요) — 생성 지시문 저장은 됩니다."] : []),
    ...(quota && quota.enabled && quota.remaining <= 0 ? ["오늘 생성 한도를 다 썼습니다(한국 시간 0시 초기화)."] : []),
  ];
  // 로그인은 버튼을 잠그지 않는다 — 누르면 로그인 안내가 뜬다(기존 동작). 다만 미리 알린다.
  const reasons = [...lockReasons, ...(loadToken() ? [] : ["로그인해야 이미지를 만들 수 있습니다."])];
  const reasonsId = useId();

  function refreshQuota() {
    const token = loadToken();
    if (!token) return;
    getInteriorQuota(token)
      .then((q) => setQuota({ enabled: q.enabled, limit: q.limit, remaining: q.remaining }))
      .catch(() => { /* 한도 조회 실패는 생성을 막지 않는다 — 서버가 생성 때 다시 판정한다 */ });
  }
  useEffect(() => {
    const token = loadToken();
    if (!token) return;
    const ctrl = new AbortController();
    getInteriorQuota(token, ctrl.signal)
      .then((q) => { if (!ctrl.signal.aborted) setQuota({ enabled: q.enabled, limit: q.limit, remaining: q.remaining }); })
      .catch(() => { /* 위와 같다 */ });
    return () => ctrl.abort();
  }, []);

  function toggleKeyword(ko: string) {
    setKeywords((old) => old.includes(ko) ? old.filter((k) => k !== ko) : old.length >= MAX_KEYWORDS ? old : [...old, ko]);
  }

  async function addFile(file: File | undefined, kind: Reference["kind"]) {
    if (!file) return;
    setError("");
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 3_000_000) {
      setError("PNG·JPEG·WebP 이미지(각 3MB 이하)만 올려주세요."); return;
    }
    const reader = new FileReader();
    reader.onload = () => setReferences((old) => [...old.filter((r) => r.kind !== kind), {
      kind, mime: file.type, data: String(reader.result).split(",")[1], name: file.name,
    }]);
    reader.onerror = () => setError("이미지를 읽지 못했습니다.");
    reader.readAsDataURL(file);
  }
  /** consentNow — 동의 체크 직후엔 state 가 아직 false 라 체크 값을 직접 넘긴다 */
  async function generate(consentNow = consent) {
    const token = loadToken();
    if (!token) { setError("이미지를 생성하려면 로그인하세요. 지시문 저장은 로그인 없이 할 수 있습니다."); return; }
    if (!ownDistrict.trim() || !ownIndustry.trim() || !effectiveStyle.trim() || !consentNow || pending.current || blocked) return;
    if (request.constraints.length > 1500 || effectiveStyle.length > 500) {
      setError("선택한 디자인과 직접 입력한 조건이 너무 깁니다. 구조·운영 제약이나 분위기를 줄여주세요. 지시문은 저장할 수 있습니다."); return;
    }
    if (request.links.length > 5 || request.links.some((url) => { try { return !["http:", "https:"].includes(new URL(url).protocol); } catch { return true; } })) {
      setError("참고 링크는 http·https 주소로 최대 5개 입력하세요."); return;
    }
    pending.current = true; setBusy(true); setError("");
    try {
      const image = await generateInterior(token, request);
      setResult({ image, prompt: `${brief}\n${designBrief}` });
      if (image.daily_limit != null && image.remaining_today != null) {
        setQuota({ enabled: true, limit: image.daily_limit, remaining: image.remaining_today });
      }
    }
    catch (err) { setError(interiorErrorMessage(err)); refreshQuota(); }
    finally { pending.current = false; setBusy(false); }
  }
  const visibleGroups = INTERIOR_KEYWORD_GROUPS.filter((g) => category === "all" || g.id === category);
  return <section className="interior-planner" aria-label="인테리어 참고안">
    <h2>인테리어 참고안</h2>
    <p>비용 비교를 확인하고 분위기를 정하세요. 상권·업종에 어울리는지는 고객 반응으로 검증할 가설입니다.</p>
    {scenarios && <div className="interior-table"><table><caption>Posting의 세 전략 계산 · 실측 매출·견적 아님</caption>
      <thead><tr><th>전략</th><th>초기 투자</th><th>월 순익</th><th>회수기간</th></tr></thead>
      <tbody>{STRATEGIES.map(([key, label]) => {
        const t = scenarios[key];
        return <tr key={key}><th scope="row">{label}</th>{t && tierAvailable(t)
          ? <><td>{(t.invest_mn * 100).toLocaleString("ko-KR")}만원</td><td>{t.month_net.toLocaleString("ko-KR")}만원</td><td>{t.viable ? `${t.roi_months}개월` : "회수 불가"}</td></>
          : <td colSpan={3}>자료 부족</td>}</tr>;
      })}</tbody></table></div>}
    <fieldset disabled={busy}>
      <legend>사용자 조건</legend>
      <InteriorDesignControls value={design} onChange={setDesign} />
      <div className="interior-fields">
        <label>상권<input value={ownDistrict} maxLength={100} onChange={(e) => setOwnDistrict(e.target.value)} /></label>
        <label>디자인할 업종<input value={ownIndustry} maxLength={100} onChange={(e) => setOwnIndustry(e.target.value)} /></label>
        <label>인테리어 전략<select value={strategy} onChange={(e) => setStrategy(e.target.value as Strategy)}>{STRATEGIES.map(([, label]) => <option key={label}>{label}</option>)}</select></label>
      </div>
      <fieldset className="interior-keywords">
        <legend>분위기·색감 키워드</legend>
        <div className="interior-filter" role="group" aria-label="키워드 분류">
          {CATEGORIES.map(([id, label]) => <button type="button" key={id} aria-pressed={category === id} onClick={() => setCategory(id)}>{label}</button>)}
        </div>
        {visibleGroups.map((g) => <div key={g.id} className="interior-keyword-group" role="group" aria-label={`${g.label} 키워드`}>
          <p className="interior-keyword-title">{g.label}</p>
          <div className="interior-chips">{g.keywords.map((k) => {
            const on = keywords.includes(k.ko);
            return <button type="button" key={k.ko} aria-pressed={on} title={k.en}
              disabled={!on && keywords.length >= MAX_KEYWORDS} onClick={() => toggleKeyword(k.ko)}>{k.ko}</button>;
          })}</div>
        </div>)}
        <p className="interior-selected" role="status">
          고른 키워드 {keywords.length}/{MAX_KEYWORDS}: {keywords.length ? keywords.join(", ") : "아직 없음 — 위에서 골라 주세요"}
          {keywords.length > 0 && <button type="button" onClick={() => setKeywords([])}>선택 초기화</button>}
        </p>
        <label>직접 추가할 키워드 (선택)<input value={extra} maxLength={EXTRA_MAX} placeholder="예: 큰 창, 오픈 주방, 바 좌석" onChange={(e) => setExtra(e.target.value)} /></label>
      </fieldset>
      <label>보존할 구조·운영 제약<textarea value={constraints} maxLength={1500} onChange={(e) => setConstraints(e.target.value)} placeholder="출입구·기둥·채광·주방·설비·예산 등 확인한 내용" /></label>
      <label>참고 링크 (한 줄에 하나 · 최대 5개)<textarea value={links} maxLength={3000} onChange={(e) => setLinks(e.target.value)} /></label>
      <p>링크는 참고 메모로 전달하며 내용을 자동으로 읽지 않습니다. 반영할 디자인은 사진으로 올려주세요.</p>
      <div className="interior-fields">{(["plan", "photo"] as const).map((kind) => <label key={kind}>{kind === "plan" ? "내부 도면 이미지" : "현장·디자인 참고 사진"}
        <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => { void addFile(e.target.files?.[0], kind); e.target.value = ""; }} />
      </label>)}</div>
      <div className="interior-references">{references.map((r) => <figure key={r.kind}>
        <img src={`data:${r.mime};base64,${r.data}`} alt={`사용자 제공 ${r.kind === "plan" ? "도면" : "참고 사진"}`} />
        <figcaption>사용자 제공 · {r.name} <button type="button" onClick={() => setReferences((old) => old.filter((x) => x.kind !== r.kind))}>제거</button></figcaption>
      </figure>)}</div>
      <label className="interior-consent"><input type="checkbox" checked={consent} onChange={(e) => {
        const checked = e.target.checked;
        setConsent(checked);
        // 동의하면 버튼 없이 바로 한 장 만든다(2026-11-06 사용자 결정). 조건을 바꿔도 자동으로 다시 만들지 않는다 —
        // 생성마다 공급자 비용이 들고, 하루 5회 한도를 쓴다. 다시 만들기는 버튼으로.
        if (checked && !result) void generate(true);
      }} />이미지 생성에 입력 내용·사진을 외부 AI(OpenAI)로 보내는 데 동의합니다. 동의하면 바로 참고 이미지를 만듭니다. 생성 비용은 서비스 설정에 따릅니다.</label>
      {quota && <p className="interior-quota" role="status">{!quota.enabled
        ? "이 서버에는 아직 이미지 생성이 설정되지 않았습니다(운영자 설정 필요). 생성 지시문은 저장해 쓸 수 있습니다."
        : quota.remaining > 0
          ? `오늘 남은 이미지 생성 ${quota.remaining}/${quota.limit}회 · 한국 시간 0시에 초기화됩니다.`
          : `오늘 이미지 생성 한도(${quota.limit}회)를 모두 사용했습니다. 내일 0시(한국 시간)에 다시 만들 수 있습니다. 생성 지시문은 저장할 수 있습니다.`}</p>}
      <div className="interior-actions">
        <button type="button" onClick={() => {
          try {
            localStorage.setItem(`placeos.interior-brief.${handoff?.districtId ?? district ?? ""}`, JSON.stringify({ brief: `${brief}\n${designBrief}`, design, source: "user_input", unitId: handoff?.unitId ?? null }));
            setSaved("인테리어 조건을 이 브라우저에 저장했습니다. 검증 리포트에 포함됩니다.");
          } catch { setSaved("저장하지 못했습니다. 브라우저 저장 공간을 확인하세요."); }
        }}>리포트에 인테리어 조건 저장</button>
        <button type="button" disabled={lockReasons.length > 0} aria-describedby={reasons.length && !busy ? reasonsId : undefined}
          onClick={() => { void generate(); }}>{busy ? "이미지 생성 중…" : result || error ? "다시 만들기" : "AI 참고 이미지 생성"}</button>
        <button type="button" onClick={() => download("placeos-interior-brief.json", JSON.stringify({ source: "user_input", brief: `${brief}\n${designBrief}`, design, posting: handoff?.calculation ?? null }, null, 2))}>생성 지시문·비용 결과 저장</button>
        <a href="https://www.canva.com/ai/" target="_blank" rel="noopener noreferrer">Canva에서 직접 만들기 ↗</a>
      </div>
      {!busy && reasons.length > 0 && <div className="interior-why" id={reasonsId}>
        <b>지금 AI 이미지를 만들 수 없는 이유</b>
        <ul>{reasons.map((r) => <li key={r}>{r}</li>)}</ul>
      </div>}
    </fieldset>
    {error && <p role="alert">{error}</p>}
    {saved && <p role="status">{saved}</p>}
    {result && <figure className="interior-result"><img src={result.image.image_data_url} alt="AI 생성 인테리어 참고 이미지 · 실측·시공안 아님" />
      <figcaption>{result.image.note} <a href={result.image.image_data_url} download="placeos-interior-ai.png">이미지 저장</a></figcaption>
      <details><summary>이 이미지 생성에 쓴 조건</summary><pre>{result.prompt}</pre></details>
    </figure>}
    <p>확인할 것: 도면 치수와 피난·접근 동선, 업종별 설비, 실제 견적, 목표 고객의 반응. 생성 이미지로 적합성·성과를 확정하지 않습니다.</p>
  </section>;
}
