import { useRef, useState } from "react";
import { generateInterior, interiorErrorMessage, tierAvailable, type InteriorImage } from "@/lib/api";
import { loadToken } from "@/lib/session";
import type { ProgramHandoff } from "@/lib/workspaceState";
import "./InteriorPlanner.css";

type Strategy = "고급화" | "가성비" | "기능중심";
type Reference = { kind: "plan" | "photo"; mime: string; data: string; name: string };
const STYLES = ["빈티지", "가을", "따뜻함", "깔끔함", "자연 소재", "미니멀"];
const STRATEGIES: [string, Strategy][] = [["premium", "고급화"], ["value", "가성비"], ["factory", "기능중심"]];

function download(name: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** 사용자 조건과 Posting 계산을 명시해 생성한다. 어울림 점수·내부 치수·시공 견적은 만들지 않는다. */
export default function InteriorPlanner({ handoff, district, industry }: {
  handoff?: ProgramHandoff; district?: string | null; industry?: string;
}) {
  const [style, setStyle] = useState("");
  const [strategy, setStrategy] = useState<Strategy>(
    STRATEGIES.find(([, label]) => label === handoff?.strategy)?.[1] ?? "가성비");
  const [constraints, setConstraints] = useState("");
  const [links, setLinks] = useState("");
  const [references, setReferences] = useState<Reference[]>([]);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ image: InteriorImage; prompt: string } | null>(null);
  const selectedDistrict = handoff?.districtName ?? handoff?.districtId ?? district ?? "";
  const selectedIndustry = handoff?.industry ?? industry ?? "";
  const [ownDistrict, setOwnDistrict] = useState(selectedDistrict);
  const [ownIndustry, setOwnIndustry] = useState(selectedIndustry);
  const scenarios = handoff?.calculation?.result.scenarios;
  const request = {
    district: ownDistrict, industry: ownIndustry, style, strategy,
    ...(handoff?.area ? { area_py: handoff.area } : {}),
    constraints, links: links.split("\n").map((s) => s.trim()).filter(Boolean),
    references: references.map(({ kind, mime, data }) => ({ kind, mime, data })), consent: true as const,
  };
  const brief = `AI 인테리어 참고안 · 실측 도면·시공안 아님\n상권: ${ownDistrict}\n업종: ${ownIndustry}\n자리: ${handoff?.unitName ?? "미선택"}\n면적: ${handoff?.area ?? "미확인"}평\n전략: ${strategy}\n분위기: ${style}\n보존할 구조·운영 제약: ${constraints || "미입력"}\n참고 링크(원문 미확인): ${links || "없음"}\n사용자 참고 이미지: ${references.map((r) => `${r.kind} ${r.name}`).join(", ") || "없음"}\n도면의 벽·기둥·출입구를 보존하고, 확인되지 않은 치수·수요·매출·법규 적합성을 주장하지 말 것.`;

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
  async function generate() {
    const token = loadToken();
    if (!token) { setError("이미지를 생성하려면 로그인하세요. 지시문 저장은 로그인 없이 할 수 있습니다."); return; }
    if (!ownDistrict.trim() || !ownIndustry.trim() || !style.trim() || !consent || pending.current) return;
    if (request.links.length > 5 || request.links.some((url) => { try { return !["http:", "https:"].includes(new URL(url).protocol); } catch { return true; } })) {
      setError("참고 링크는 http·https 주소로 최대 5개 입력하세요."); return;
    }
    pending.current = true; setBusy(true); setError("");
    try { setResult({ image: await generateInterior(token, request), prompt: brief }); }
    catch (err) { setError(interiorErrorMessage(err)); }
    finally { pending.current = false; setBusy(false); }
  }
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
      <div className="interior-fields">
        <label>상권<input value={ownDistrict} maxLength={100} onChange={(e) => setOwnDistrict(e.target.value)} /></label>
        <label>디자인할 업종<input value={ownIndustry} maxLength={100} onChange={(e) => setOwnIndustry(e.target.value)} /></label>
        <label>인테리어 전략<select value={strategy} onChange={(e) => setStrategy(e.target.value as Strategy)}>{STRATEGIES.map(([, label]) => <option key={label}>{label}</option>)}</select></label>
        <label>분위기·색감<input value={style} maxLength={500} placeholder="예: 따뜻함, 나무, 밝은 베이지" onChange={(e) => setStyle(e.target.value)} /></label>
      </div>
      <div className="interior-chips">{STYLES.map((s) => <button type="button" key={s} onClick={() => setStyle(s)}>{s}</button>)}</div>
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
      <label className="interior-consent"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />이미지 생성 시 입력 내용·사진을 외부 AI(OpenAI)에 전송하는 데 동의합니다. 생성 비용은 서비스 설정에 따릅니다.</label>
      <div className="interior-actions">
        <button type="button" disabled={!ownDistrict.trim() || !ownIndustry.trim() || !style.trim() || !consent} onClick={() => { void generate(); }}>{busy ? "이미지 생성 중…" : "AI 참고 이미지 생성"}</button>
        <button type="button" onClick={() => download("placeos-interior-brief.json", JSON.stringify({ source: "user_input", brief, posting: handoff?.calculation ?? null }, null, 2))}>생성 지시문·비용 결과 저장</button>
        <a href="https://www.canva.com/ai/" target="_blank" rel="noopener noreferrer">Canva에서 직접 만들기 ↗</a>
      </div>
    </fieldset>
    {error && <p role="alert">{error}</p>}
    {result && <figure className="interior-result"><img src={result.image.image_data_url} alt="AI 생성 인테리어 참고 이미지 · 실측·시공안 아님" />
      <figcaption>{result.image.note} <a href={result.image.image_data_url} download="placeos-interior-ai.png">이미지 저장</a></figcaption>
      <details><summary>이 이미지 생성에 쓴 조건</summary><pre>{result.prompt}</pre></details>
    </figure>}
    <p>확인할 것: 도면 치수와 피난·접근 동선, 업종별 설비, 실제 견적, 목표 고객의 반응. 생성 이미지로 적합성·성과를 확정하지 않습니다.</p>
  </section>;
}
