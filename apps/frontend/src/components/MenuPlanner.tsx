import { Fragment, useEffect, useId, useState } from "react";
import {
  getMenuBenchmarks, tierAvailable, type MenuBenchmarkCategory, type MenuBenchmarks, type MenuBenchmarkValue, type MenuOwnershipGroup, type TierScenario,
} from "@/lib/api";
import {
  dailyFromRevenue, emptyEquipment, emptyIngredient, emptyMenuRow, equipmentPlan, ingredientCost, ingredientsTotal, menuBep, menuCategoryOf, menuMix, menuRowsFromBenchmark,
  mergeIntoBlanks, perHour,
  type EquipmentRow, type IngredientRow, type MenuRow,
} from "@/lib/menuPlan";
import "./PostingSteps.css";

const TIER_NAME: Record<string, string> = { premium: "고급화", value: "가성비", factory: "기능중심" };
const MAX_ROWS = 8;
const MAX_SUB = 10;
/** 대표메뉴로 채울 때 넣는 메뉴 수 */
const MENU_FILL = 4;
const n0 = (v: number) => Math.round(v).toLocaleString("ko-KR");
const n1 = (v: number) => (Math.round(v * 10) / 10).toLocaleString("ko-KR");
const digits = (v: string) => v.replace(/[^\d.]/g, "");

type Own = "independent" | "franchise";
type Row = MenuRow & { id: number; ingredients: IngredientRow[] };
let nextId = 1;
const newRow = (): Row => ({ ...emptyMenuRow(), id: nextId++, ingredients: [emptyIngredient()] });
const blankRow = (r: MenuRow) => ![r.name, r.price, r.cost, r.share].some((v) => v.trim());
const blankEquip = (e: EquipmentRow) => ![e.name, e.price, e.years].some((v) => v.trim());
/** 빈칸 채우기가 다루는 칸 — 같은 값 키를 업종 평균 · 운영형태 평균 어느 쪽에서든 읽는다 */
const FILL_FIELDS = [
  { key: "open_days", label: "월 영업일", fmt: (v: number) => String(Math.round(v)) },
  { key: "open_hours", label: "하루 영업 시간", fmt: (v: number) => String(v) },
  { key: "labor_month", label: "인건비", fmt: (v: number) => String(Math.round(v)) },
] as const;

/**
 * Posting 「메뉴 설정」(2026-11-10) — 대표 메뉴로 객단가 · 원가율을 잡고 하루 손익분기 판매 개수를 낸다. 계산은 `lib/menuPlan`.
 *
 * 2026-11-26 사용자 요청 「선택한 업종을 (개인사업, 가맹점)에 맞는 메뉴, 판매가, 원가, 비중 평균값 제시 및 재료값, 장비값 예시 설정란 제공,
 * 월 영업일, 영업 시간, 고정비 예시」:
 *   · 운영 형태(개인사업 · 가맹점) — 가맹점이면 로열티(매출의 %) · 광고분담금 칸이 더해진다
 *   · 업종 평균(`GET /ai/menu-benchmarks` — 농식품부 2025 외식업체 경영실태 조사 + KOSIS 서울) — 출처가 있는 값만 보이고, 누를 때만 빈칸에 넣는다:
 *     「대표메뉴로 메뉴 표 채우기」(판매가 = 대표메뉴 평균 가격 · 원가 = 판매가 × 업종 식재료비 비율 추정 · 비중 = 응답 수 비중, 판매 비중 아님) ·
 *     「업종 평균으로 빈칸 채우기」 · 「개인사업/가맹점 평균으로 빈칸 채우기」(외식업 전체 — 보고서에 업종 × 운영형태 교차가 없다) · 「업종 평균 장비값 넣기」
 *   · 재료값 — 메뉴마다 재료로 1개 원가를 계산해 「원가 칸에 넣기」 · 장비값 — 구입가 ÷ 쓸 햇수 ÷ 12 를 월 고정비에 더한다
 *   · 월 영업일 · 하루 영업 시간 · 고정비(인건비 · 관리비 · 기타) — 예시는 칸 안의 흐린 글씨(placeholder)로만, 출처가 있는 평균이면 그 값으로
 */
export default function MenuPlanner({ rent, rentSource, scenarios, industry, detailKey }: {
  /** 계산에 쓴 월 임대료(만원) — 왼쪽에서 고른 자리 */
  rent?: number | null; rentSource?: string | null; scenarios?: Record<string, TierScenario> | null;
  /** 왼쪽 「업종」 입력 · 세부 업종 — 업종 평균을 어느 업종으로 볼지 처음 고르는 데만 쓴다 */
  industry?: string | null; detailKey?: string | null;
}) {
  const id = useId();
  const [rows, setRows] = useState<Row[]>(() => [newRow(), newRow(), newRow()]);
  const [openRow, setOpenRow] = useState<number | null>(null);
  const [equipment, setEquipment] = useState<EquipmentRow[]>(() => [emptyEquipment(), emptyEquipment()]);
  const [own, setOwn] = useState<Own>("independent");
  const [days, setDays] = useState("");
  const [hours, setHours] = useState("");
  const [labor, setLabor] = useState("");
  const [utilities, setUtilities] = useState("");
  const [other, setOther] = useState("");
  const [royalty, setRoyalty] = useState("");
  const [adFee, setAdFee] = useState("");
  const [bench, setBench] = useState<MenuBenchmarks | null>(null);
  const [benchFailed, setBenchFailed] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getMenuBenchmarks().then((b) => { if (live) setBench(b); }).catch(() => { if (live) setBenchFailed(true); });
    return () => { live = false; };
  }, []);
  const known = bench?.categories.map((c) => c.key) ?? [];
  const categoryKey = picked ?? menuCategoryOf(industry, detailKey, known);
  const category = bench?.categories.find((c) => c.key === categoryKey) ?? null;
  const valueOf = (key: string) => category?.values.find((v) => v.key === key) ?? null;

  const mix = menuMix(rows);
  const equip = equipmentPlan(equipment);
  const franchise = own === "franchise";
  const fixedFields = franchise ? [labor, utilities, other, adFee] : [labor, utilities, other];
  const fixedReady = fixedFields.every((v) => v.trim() !== "");
  const fixedSum = fixedReady ? fixedFields.reduce((t, v) => t + Number(v), 0) : null;
  const royaltyRate = franchise ? (royalty.trim() ? Number(royalty) / 100 : null) : 0;
  const bep = mix && rent != null && days.trim() && fixedSum != null && royaltyRate != null
    ? menuBep({ rent, otherFixed: fixedSum + (equip?.monthly ?? 0), avgPrice: mix.avgPrice, costRate: mix.costRate, days: Number(days), royaltyRate })
    : null;
  const hourly = bep && hours.trim() ? perHour(bep.dailySales, Number(hours)) : null;

  const set = (i: number, k: keyof MenuRow, v: string) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: k === "name" ? v : digits(v) } : r)));
  const setIngredient = (rowId: number, i: number, k: keyof IngredientRow, v: string) => setRows((rs) => rs.map((r) => (r.id !== rowId ? r
    : { ...r, ingredients: r.ingredients.map((g, j) => (j === i ? { ...g, [k]: k === "name" ? v : digits(v) } : g)) })));
  const setEquip = (i: number, k: keyof EquipmentRow, v: string) => setEquipment((es) => es.map((e, j) => (j === i ? { ...e, [k]: k === "name" ? v : digits(v) } : e)));
  const tiers = Object.entries(scenarios ?? {}).filter(([, s]) => tierAvailable(s));

  // 빈칸 채우기 — 출처가 있는 평균이 있고 칸이 비어 있을 때만(기존 입력은 그대로 둔다)
  const fieldState: Record<(typeof FILL_FIELDS)[number]["key"], [string, (v: string) => void]> = {
    open_days: [days, setDays], open_hours: [hours, setHours], labor_month: [labor, setLabor],
  };
  const fillablesFrom = (values: MenuBenchmarkValue[] | undefined) => FILL_FIELDS
    .map((f) => ({ ...f, v: values?.find((x) => x.key === f.key) }))
    .filter((f) => f.v && !fieldState[f.key][0].trim());
  const fillFrom = (list: ReturnType<typeof fillablesFrom>) => { for (const f of list) fieldState[f.key][1](f.fmt(f.v!.value)); };
  const ownGroup = bench?.ownership.groups.find((g) => g.key === own) ?? null;
  const industryFill = fillablesFrom(category?.values);
  const ownershipFill = fillablesFrom(ownGroup?.values);
  const daysHint = valueOf("open_days");
  const hoursHint = valueOf("open_hours");
  const laborHint = valueOf("labor_month");
  const menus = category?.menus ?? null;
  const menuIncoming = menus ? menuRowsFromBenchmark(menus.items, menus.cost_rate.value, MENU_FILL) : [];
  const menuFillable = menuIncoming.some((m) => !rows.some((r) => !blankRow(r) && r.name.trim() === m.name)) && (rows.some(blankRow) || rows.length < MAX_ROWS);
  const fillMenus = () => setRows((rs) => mergeIntoBlanks<Row>(rs, menuIncoming.map((m) => ({ ...newRow(), ...m })), blankRow, (r) => r.name.trim(), MAX_ROWS));
  const kitchen = valueOf("invest_kitchen");
  const hall = valueOf("invest_hall");
  const equipIncoming: EquipmentRow[] = [
    kitchen && { name: "주방 관련(업종 평균)", price: String(kitchen.value), years: "" },
    hall && { name: "홀 관련(업종 평균)", price: String(hall.value), years: "" },
  ].filter(Boolean) as EquipmentRow[];
  const equipFillable = equipIncoming.some((e) => !equipment.some((x) => x.name.trim() === e.name)) && (equipment.some(blankEquip) || equipment.length < MAX_SUB);
  const fillEquipment = () => setEquipment((es) => mergeIntoBlanks(es, equipIncoming, blankEquip, (e) => e.name.trim(), MAX_SUB));

  // 식재료비(2026-11-27) — 메뉴 줄마다 들어 있는 재료(rows[].ingredients)를 한 표로 펼친다. 메뉴 줄의 「재료값」과 **같은 값**을 고친다
  const menuName = (r: Row, i: number) => r.name.trim() || `메뉴 ${i + 1}`;
  const foodLines = rows.flatMap((r, i) => r.ingredients.map((g, j) => ({ rowId: r.id, menuIndex: i, j, g })));
  const moveIngredient = (fromId: number, j: number, toId: number) => setRows((rs) => {
    const item = rs.find((x) => x.id === fromId)?.ingredients[j];
    const target = rs.find((x) => x.id === toId);
    if (!item || fromId === toId || !target || target.ingredients.length >= MAX_SUB) return rs;
    return rs.map((x) => (x.id === fromId ? { ...x, ingredients: x.ingredients.filter((_, k) => k !== j) }
      : x.id === toId ? { ...x, ingredients: [...x.ingredients, item] } : x));
  });
  const removeIngredient = (rowId: number, j: number) =>
    setRows((rs) => rs.map((x) => (x.id !== rowId ? x : { ...x, ingredients: x.ingredients.filter((_, k) => k !== j) })));
  // 새 줄은 표 맨 아래에 — 재료가 있는 마지막 메뉴 묶음 뒤에 붙인다(다른 메뉴 것이면 「쓰는 메뉴」로 옮긴다)
  const addFoodTarget = [...rows].reverse().find((r) => r.ingredients.length > 0 && r.ingredients.length < MAX_SUB)
    ?? rows.find((r) => r.ingredients.length < MAX_SUB);
  const addFoodLine = () => { if (addFoodTarget) setRows((rs) => rs.map((x) => (x.id !== addFoodTarget.id ? x : { ...x, ingredients: [...x.ingredients, emptyIngredient()] }))); };
  const perMenuFood = rows.map((r, i) => ({ r, i, sub: ingredientsTotal(r.ingredients) })).filter((x) => x.sub);
  const foodToCostPending = perMenuFood.some(({ r, sub }) => r.cost.trim() !== String(Math.round(sub!.total)));
  const putFoodIntoCosts = () => setRows((rs) => rs.map((r) => { const sub = ingredientsTotal(r.ingredients); return sub ? { ...r, cost: String(Math.round(sub.total)) } : r; }));
  const foodMix = category?.food_mix ?? null;
  const foodRate = valueOf("food_cost_rate");

  const missingInputs = [
    !days.trim() && "월 영업일(1~31)", !labor.trim() && "인건비", !utilities.trim() && "관리비 · 공과금", !other.trim() && "기타 월 고정비",
    franchise && !royalty.trim() && "로열티", franchise && !adFee.trim() && "광고분담금",
  ].filter(Boolean) as string[];

  return (
    <section className="pstep" aria-label="메뉴로 본 손익분기">
      <p className="pstep-lede">운영 형태를 고르고, 업종 평균은 참고로만 보세요 — 누를 때만 빈칸에 들어가요.</p>

      <div className="pstep-own" role="radiogroup" aria-label="운영 형태">
        {([["independent", "개인사업", "메뉴 · 판매가 · 원가를 내가 정해요"], ["franchise", "가맹점", "가맹본부가 정한 메뉴 · 판매가 · 공급가와 로열티를 넣어요"]] as const).map(([k, label, sub]) => (
          <label key={k} className={own === k ? "is-on" : undefined}>
            <input type="radio" name={`${id}-own`} value={k} checked={own === k} onChange={() => setOwn(k)} />
            <span><b>{label}</b><small>{sub}</small></span>
          </label>
        ))}
      </div>

      <BenchmarkCard bench={bench} failed={benchFailed} category={category} categoryKey={categoryKey} onPick={setPicked} own={own}
        industryFill={industryFill.length ? { label: industryFill.map((f) => f.label).join(" · "), run: () => fillFrom(industryFill) } : undefined}
        ownershipFill={ownershipFill.length && ownGroup ? { label: ownershipFill.map((f) => f.label).join(" · "), run: () => fillFrom(ownershipFill) } : undefined}
        menuFill={menuFillable ? fillMenus : undefined} equipFill={equipFillable ? fillEquipment : undefined} />

      <h3 className="pstep-h">메뉴 <small>{franchise ? "가맹본부 정보공개서 · 가맹계약서의 판매가 · 공급가(원가)를 넣으세요" : "대표 메뉴 3~5개면 충분해요"}</small></h3>
      <div className="pstep-table">
        <table>
          <thead><tr><th scope="col">메뉴</th><th scope="col">판매가(원)</th><th scope="col">원가(원)</th><th scope="col">판매 비중(%)</th><th scope="col"><span className="sr-only">재료로 원가 계산</span></th><th scope="col"><span className="sr-only">삭제</span></th></tr></thead>
          <tbody>{rows.map((r, i) => {
            const open = openRow === r.id;
            const sub = ingredientsTotal(r.ingredients);
            return <Fragment key={r.id}>
              <tr>
                <td><input aria-label={`메뉴 ${i + 1} 이름`} value={r.name} onChange={(e) => set(i, "name", e.target.value)} placeholder={`메뉴 ${i + 1}`} /></td>
                <td><input aria-label={`메뉴 ${i + 1} 판매가`} inputMode="numeric" value={r.price} onChange={(e) => set(i, "price", e.target.value)} placeholder="원" /></td>
                <td><input aria-label={`메뉴 ${i + 1} 원가`} inputMode="numeric" value={r.cost} onChange={(e) => set(i, "cost", e.target.value)} placeholder="재료 · 포장" /></td>
                <td><input aria-label={`메뉴 ${i + 1} 판매 비중`} inputMode="numeric" value={r.share} onChange={(e) => set(i, "share", e.target.value)} placeholder="%" /></td>
                <td><button type="button" className="pstep-mini" aria-expanded={open} aria-label={`메뉴 ${i + 1} 재료값으로 원가 계산`}
                  onClick={() => setOpenRow(open ? null : r.id)}>재료값</button></td>
                <td>{rows.length > 1 && <button type="button" className="pstep-x" aria-label={`메뉴 ${i + 1} 지우기`} onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}>×</button>}</td>
              </tr>
              {open && <tr className="pstep-subrow"><td colSpan={6}>
                <div className="pstep-ingr" role="group" aria-label={`메뉴 ${i + 1} 재료값`}>
                  <p className="pstep-foot">산 양과 쓰는 양은 같은 단위(g · ml · 개)로 적어요. 계산 예) 1,000g을 25,000원에 사서 한 개에 20g 쓰면 500원.</p>
                  <table>
                    <thead><tr><th scope="col">재료</th><th scope="col">산 값(원)</th><th scope="col">산 양</th><th scope="col">1개에 쓰는 양</th><th scope="col"><span className="sr-only">삭제</span></th></tr></thead>
                    <tbody>{r.ingredients.map((g, j) => (
                      <tr key={j}>
                        <td><input aria-label={`메뉴 ${i + 1} 재료 ${j + 1} 이름`} value={g.name} onChange={(e) => setIngredient(r.id, j, "name", e.target.value)} placeholder="예: 원두 · 컵" /></td>
                        <td><input aria-label={`메뉴 ${i + 1} 재료 ${j + 1} 산 값`} inputMode="numeric" value={g.price} onChange={(e) => setIngredient(r.id, j, "price", e.target.value)} placeholder="원" /></td>
                        <td><input aria-label={`메뉴 ${i + 1} 재료 ${j + 1} 산 양`} inputMode="numeric" value={g.pack} onChange={(e) => setIngredient(r.id, j, "pack", e.target.value)} placeholder="g · ml · 개" /></td>
                        <td><input aria-label={`메뉴 ${i + 1} 재료 ${j + 1} 1개에 쓰는 양`} inputMode="numeric" value={g.use} onChange={(e) => setIngredient(r.id, j, "use", e.target.value)} placeholder="같은 단위" /></td>
                        <td>{r.ingredients.length > 1 && <button type="button" className="pstep-x" aria-label={`메뉴 ${i + 1} 재료 ${j + 1} 지우기`}
                          onClick={() => setRows((rs) => rs.map((x) => (x.id !== r.id ? x : { ...x, ingredients: x.ingredients.filter((_, k) => k !== j) })))}>×</button>}</td>
                      </tr>))}</tbody>
                  </table>
                  <p className="pstep-ingr-foot">
                    {r.ingredients.length < MAX_SUB && <button type="button" className="pstep-add"
                      onClick={() => setRows((rs) => rs.map((x) => (x.id !== r.id ? x : { ...x, ingredients: [...x.ingredients, emptyIngredient()] })))}>+ 재료 더하기</button>}
                    {sub ? <>
                      <span>메뉴 1개 재료값 <b>{n0(sub.total)}원</b> <small>재료 {sub.n}개</small></span>
                      <button type="button" className="pstep-mini is-strong" onClick={() => set(i, "cost", String(Math.round(sub.total)))}>원가 칸에 넣기</button>
                    </> : <span className="pstep-sub">산 값 · 산 양 · 쓰는 양을 한 줄 이상 채우면 재료값을 계산해요.</span>}
                  </p>
                </div>
              </td></tr>}
            </Fragment>;
          })}</tbody>
        </table>
      </div>
      {rows.length < MAX_ROWS && <button type="button" className="pstep-add" onClick={() => setRows((rs) => [...rs, newRow()])}>+ 메뉴 더하기</button>}

      <h3 className="pstep-h">식재료비 <small>메뉴마다 1개에 쓰는 재료를 적으면 메뉴 1개 재료값(원가)을 계산해요 · 산 양과 쓰는 양은 같은 단위(g · ml · 개)</small></h3>
      <div className="pstep-table" role="group" aria-label="식재료비">
        <table>
          <thead><tr><th scope="col">식재료</th><th scope="col">쓰는 메뉴</th><th scope="col">산 값(원)</th><th scope="col">산 양</th><th scope="col">1개에 쓰는 양</th><th scope="col">1개 재료값</th><th scope="col"><span className="sr-only">삭제</span></th></tr></thead>
          <tbody>{foodLines.map(({ rowId, menuIndex, j, g }, k) => {
            const one = ingredientCost(g);
            return (
              <tr key={`${rowId}-${j}`}>
                <td><input aria-label={`식재료 ${k + 1} 이름`} value={g.name} onChange={(e) => setIngredient(rowId, j, "name", e.target.value)} placeholder="예: 원두 · 우유 · 컵" /></td>
                <td><select aria-label={`식재료 ${k + 1} 쓰는 메뉴`} value={rowId} onChange={(e) => moveIngredient(rowId, j, Number(e.target.value))}>
                  {rows.map((r, i) => <option key={r.id} value={r.id}>{menuName(r, i)}</option>)}
                </select></td>
                <td><input aria-label={`식재료 ${k + 1} 산 값`} inputMode="numeric" value={g.price} onChange={(e) => setIngredient(rowId, j, "price", e.target.value)} placeholder="원" /></td>
                <td><input aria-label={`식재료 ${k + 1} 산 양`} inputMode="numeric" value={g.pack} onChange={(e) => setIngredient(rowId, j, "pack", e.target.value)} placeholder="g · ml · 개" /></td>
                <td><input aria-label={`식재료 ${k + 1} 1개에 쓰는 양`} inputMode="numeric" value={g.use} onChange={(e) => setIngredient(rowId, j, "use", e.target.value)} placeholder="같은 단위" /></td>
                <td className="pstep-num">{one == null ? "—" : `${n0(one)}원`}</td>
                <td><button type="button" className="pstep-x" aria-label={`식재료 ${k + 1} 지우기`} title={`${menuName(rows[menuIndex], menuIndex)}에서 빼기`} onClick={() => removeIngredient(rowId, j)}>×</button></td>
              </tr>);
          })}</tbody>
        </table>
      </div>
      <div className="pstep-ingr-foot pstep-food-foot">
        {addFoodTarget && <button type="button" className="pstep-add" onClick={addFoodLine}>+ 식재료 더하기</button>}
        {perMenuFood.length > 0 ? <>
          <span>메뉴 1개 재료값 {perMenuFood.map(({ r, i, sub }) => <b key={r.id} className="pstep-chip">{menuName(r, i)} {n0(sub!.total)}원</b>)}</span>
          {foodToCostPending && <button type="button" className="pstep-mini is-strong" onClick={putFoodIntoCosts}>메뉴 원가 칸에 넣기</button>}
        </> : <span className="pstep-sub">계산 예) 원두 1,000g을 25,000원에 사서 한 잔에 20g 쓰면 500원 — 컵 · 뚜껑처럼 팔 때마다 드는 것도 적어요.</span>}
      </div>
      {(foodRate || foodMix) && <p className="pstep-foot pstep-food-ref" aria-label="업종 평균 식재료비">
        {foodRate && <>업종 평균 식재료비 비율 <b>{foodRate.value}%</b>{mix ? <> · 내 메뉴 평균 원가율 <b>{(mix.costRate * 100).toFixed(1)}%</b></> : null}. </>}
        {foodMix && <>식재료비 구성({category!.label} · 표 {foodMix.table} {foodMix.page}쪽 · 사례 {foodMix.n.toLocaleString("ko-KR")}곳): {foodMix.items.filter((it) => it.value >= 1).map((it) => `${it.label} ${it.value}%`).join(" · ")}. {foodMix.note}</>}
      </p>}

      <h3 className="pstep-h">장비값 <small>구입가 ÷ 쓸 햇수 ÷ 12 를 한 달 고정비에 더해 계산해요</small></h3>
      <div className="pstep-table" role="group" aria-label="장비값">
        <table>
          <thead><tr><th scope="col">장비</th><th scope="col">구입가(만원)</th><th scope="col">쓸 햇수(년)</th><th scope="col"><span className="sr-only">삭제</span></th></tr></thead>
          <tbody>{equipment.map((e, i) => (
            <tr key={i}>
              <td><input aria-label={`장비 ${i + 1} 이름`} value={e.name} onChange={(ev) => setEquip(i, "name", ev.target.value)} placeholder="예: 커피 머신 · 냉장고" /></td>
              <td><input aria-label={`장비 ${i + 1} 구입가`} inputMode="numeric" value={e.price} onChange={(ev) => setEquip(i, "price", ev.target.value)} placeholder="만원" /></td>
              <td><input aria-label={`장비 ${i + 1} 쓸 햇수`} inputMode="numeric" value={e.years} onChange={(ev) => setEquip(i, "years", ev.target.value)} placeholder="1~30년" /></td>
              <td>{equipment.length > 1 && <button type="button" className="pstep-x" aria-label={`장비 ${i + 1} 지우기`} onClick={() => setEquipment((es) => es.filter((_, j) => j !== i))}>×</button>}</td>
            </tr>))}</tbody>
        </table>
      </div>
      <p className="pstep-ingr-foot">
        {equipment.length < MAX_SUB && <button type="button" className="pstep-add" onClick={() => setEquipment((es) => [...es, emptyEquipment()])}>+ 장비 더하기</button>}
        {equip ? <span>장비값 합계 <b>{n0(equip.total)}만원</b> · 한 달 감가상각 <b>{n1(equip.monthly)}만원</b> <small>장비 {equip.n}개</small></span>
          : <span className="pstep-sub">계산 예) 1,200만원짜리 장비를 5년 쓰면 한 달 20만원이에요. 쓸 햇수까지 넣어야 계산해요 · 장비가 없으면 비워 두세요.</span>}
      </p>

      <h3 className="pstep-h">영업 조건 · 고정비 <small>흐린 글씨는 예시예요 — 출처가 있는 평균이면 그 값을 적었어요</small></h3>
      <div className="pstep-fields">
        <label htmlFor={`${id}-days`}><span>월 영업일 <small>일</small></span>
          <input id={`${id}-days`} inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/[^\d]/g, ""))}
            placeholder={daysHint ? `예: ${daysHint.value} (${category!.label} 평균)` : "예: 주 1회 쉬면 26"} /></label>
        <label htmlFor={`${id}-hours`}><span>하루 영업 시간 <small>시간</small></span>
          <input id={`${id}-hours`} inputMode="decimal" value={hours} onChange={(e) => setHours(digits(e.target.value))}
            placeholder={hoursHint ? `예: ${hoursHint.value} (${category!.label} 평균)` : "예: 11시~21시면 10"} /></label>
        <label htmlFor={`${id}-labor`}><span>인건비 <small>만원 · 직원 급여 · 4대보험</small></span>
          <input id={`${id}-labor`} inputMode="numeric" value={labor} onChange={(e) => setLabor(digits(e.target.value))}
            placeholder={laborHint ? `예: ${n0(laborHint.value)} (${category!.label} 평균 · 직원 몫)` : "없으면 0"} /></label>
        <label htmlFor={`${id}-util`}><span>관리비 · 공과금 <small>만원 · 전기 · 가스 · 수도</small></span>
          <input id={`${id}-util`} inputMode="numeric" value={utilities} onChange={(e) => setUtilities(digits(e.target.value))} placeholder="없으면 0" /></label>
        <label htmlFor={`${id}-other`}><span>기타 월 고정비 <small>만원 · 통신 · 보험 · 소모품 등, 임대료 제외</small></span>
          <input id={`${id}-other`} inputMode="numeric" value={other} onChange={(e) => setOther(digits(e.target.value))} placeholder="없으면 0" /></label>
        {franchise && <>
          <label htmlFor={`${id}-royalty`}><span>로열티 <small>매출의 % · 정액이면 기타 고정비에</small></span>
            <input id={`${id}-royalty`} inputMode="numeric" value={royalty} onChange={(e) => setRoyalty(digits(e.target.value))} placeholder="없으면 0" /></label>
          <label htmlFor={`${id}-ad`}><span>광고분담금 <small>만원 · 월</small></span>
            <input id={`${id}-ad`} inputMode="numeric" value={adFee} onChange={(e) => setAdFee(digits(e.target.value))} placeholder="없으면 0" /></label>
        </>}
        <p className="pstep-rent">월 임대료 {rent != null ? `${n0(rent)}만원` : "—"} <small>{rent != null ? `왼쪽에서 고른 자리 · ${rentSource === "contract" || rentSource === "user_input" ? "입력값" : "시세 추정"}` : "자리를 먼저 고르세요"}</small></p>
      </div>

      {!mix ? <p className="pstep-empty" role="status">판매가와 원가(판매가보다 작게)를 한 줄 이상 넣으면 평균 객단가를 냅니다.</p> : (
        <div className="pstep-result" aria-label="메뉴 계산 결과">
          <p>평균 객단가 <b>{n0(mix.avgPrice)}원</b> · 평균 원가율 <b>{(mix.costRate * 100).toFixed(1)}%</b>
            <small>{mix.n}개 메뉴 · {mix.weighted ? "판매 비중으로 가중" : "판매 비중이 비어 단순 평균"}</small></p>
          {!bep ? <p className="pstep-empty" role="status">{missingInputs.length
            ? `${missingInputs.join(" · ")}을(를) 넣으면 하루 손익분기 판매 개수를 계산합니다(없으면 0).`
            : rent == null ? "자리를 먼저 고르면 계산합니다." : "입력 범위를 확인해 주세요 — 월 영업일은 1~31, 원가율과 로열티를 합쳐 100% 아래여야 해요."}</p> : <>
            <p className="pstep-big">하루 <b>{bep.dailySales.toLocaleString("ko-KR")}개</b> 팔면 본전
              {hourly != null && <small>영업 {Number(hours)}시간이면 1시간에 약 {hourly.toLocaleString("ko-KR")}개</small>}</p>
            <p>월 손익분기 매출 {n0(bep.breakEvenRevenue)}만원 <small>= (임대료 {n0(rent!)}만원 + 고정비 {n0(fixedSum!)}만원{equip ? ` + 장비 감가상각 ${n1(equip.monthly)}만원` : ""})
              ÷ (1 − 원가율{franchise && royaltyRate ? " − 로열티" : ""})</small></p>
            {tiers.length > 0 && <div className="pstep-table"><table>
              <caption>시뮬레이션 결과의 추정 월매출을 이 객단가로 나누면</caption>
              <thead><tr><th scope="col">가격대</th><th scope="col">추정 월매출</th><th scope="col">하루 판매(추정)</th><th scope="col">본전 대비</th></tr></thead>
              <tbody>{tiers.map(([k, s]) => { const d = dailyFromRevenue(s.month_rev!, mix.avgPrice, Number(days)); return (
                <tr key={k}><th scope="row">{TIER_NAME[k] ?? s.name}</th><td>{n0(s.month_rev!)}만원</td><td>약 {d.toLocaleString("ko-KR")}개</td>
                  <td className={d >= bep.dailySales ? "is-pos" : "is-neg"}>{d >= bep.dailySales ? "넘는다" : "못 미친다"}</td></tr>); })}</tbody>
            </table></div>}
          </>}
          <p className="pstep-foot">판매 1건 = 메뉴 1개로 봤습니다. 원가에는 재료비 · 포장재 · 카드수수료처럼 팔 때마다 드는 돈을 넣으세요. 고정비에 대표자 본인 몫(생활비)은 들어 있지 않아요 — 본전 뒤에 남는 돈에서 가져갑니다. 추정 월매출은 상권 평균 매출(면적 비례)이라 이 메뉴의 실제 수요가 아닙니다 — 가오픈 · 시험 판매로 확인할 값입니다.</p>
        </div>
      )}
    </section>
  );
}

const OWN_KEYS = ["open_days", "open_hours", "avg_ticket", "food_cost_rate", "sales_month", "labor_month", "rent_month", "invest_total", "invest_kitchen", "invest_hall"];
const fmtValue = (v: MenuBenchmarkValue) => (v.unit === "%" ? `${v.value}%` : `${v.value.toLocaleString("ko-KR")}${v.unit}`);

/** 업종 평균 · 출처 — 확인한 값만 보이고, 누를 때만 빈칸에 넣는다. 개인사업 · 가맹점 비교는 외식업 전체 값이라고 밝힌다(업종 × 운영형태 교차 없음) */
function BenchmarkCard({ bench, failed, category, categoryKey, onPick, own, industryFill, ownershipFill, menuFill, equipFill }: {
  bench: MenuBenchmarks | null; failed: boolean; category: MenuBenchmarkCategory | null; categoryKey: string | null;
  onPick: (key: string | null) => void; own: Own;
  industryFill?: { label: string; run: () => void }; ownershipFill?: { label: string; run: () => void };
  menuFill?: () => void; equipFill?: () => void;
}) {
  const selectId = useId();
  if (failed) return <p className="pstep-empty" role="status">업종 평균을 불러오지 못했어요. 메뉴와 비용은 직접 넣어 계산할 수 있어요.</p>;
  if (!bench) return <p className="pstep-empty" role="status">업종 평균을 불러오는 중…</p>;
  const menus = category?.menus ?? null;
  const menuTotal = menus ? menus.items.reduce((t, i) => t + i.n, 0) : 0;
  const groups = bench.ownership.groups;
  const ownLabel = groups.find((g) => g.key === own)?.label ?? "";
  const cell = (g: MenuOwnershipGroup, key: string) => { const v = g.values.find((x) => x.key === key); return v ? fmtValue(v) : "—"; };
  return (
    <div className="pstep-bench" role="group" aria-label="업종 평균">
      <label htmlFor={selectId} className="pstep-bench-pick"><span>업종 평균</span>
        <select id={selectId} value={categoryKey ?? ""} onChange={(e) => onPick(e.target.value || null)}>
          <option value="">업종을 고르세요</option>
          {bench.categories.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
        </select>
      </label>
      {!category ? <p className="pstep-sub">업종을 고르면 그 업종의 대표메뉴 가격과 공식 통계 평균(출처 포함)을 보여 줘요.</p> : <>
        {menus && <div className="pstep-bench-menus" role="group" aria-label="대표메뉴 평균 가격">
          <h4>대표메뉴 평균 가격 <small>표 {menus.table} · {menus.page}쪽 · 응답 {menus.total.n.toLocaleString("ko-KR")}건</small></h4>
          <div className="pstep-table"><table>
            <thead><tr><th scope="col">메뉴</th><th scope="col">평균 판매가</th><th scope="col">추정 원가</th><th scope="col">응답 수(비중)</th></tr></thead>
            <tbody>{menus.items.map((it) => (
              <tr key={it.name}><th scope="row">{it.name}</th><td>{it.price.toLocaleString("ko-KR")}원</td>
                <td>{Math.round((it.price * menus.cost_rate.value) / 100).toLocaleString("ko-KR")}원</td>
                <td>{it.n.toLocaleString("ko-KR")}건 ({menuTotal ? Math.round((it.n / menuTotal) * 100) : 0}%)</td></tr>))}</tbody>
          </table></div>
          <p className="pstep-foot">추정 원가 = 판매가 × 이 업종 식재료비 비율 {menus.cost_rate.value}%({menus.cost_rate.detail}). {menus.note}</p>
          {menuFill && <button type="button" className="pstep-mini is-strong" onClick={menuFill}>대표메뉴로 메뉴 표 채우기 (앞 {MENU_FILL}개)</button>}
        </div>}
        {category.values.length > 0 && <ul className="pstep-bench-list">{category.values.map((v) => {
          const src = bench.sources[v.source];
          return <li key={v.key}><b>{v.label}</b> <span>{fmtValue(v)}
            {v.raw != null && v.raw !== v.value && <small> (원문 {v.raw.toLocaleString("ko-KR")}{v.unit})</small>}</span>
            <small>{src ? `${src.org} ${src.title} · ` : ""}{v.detail}</small></li>;
        })}</ul>}
        {category.notes.map((n) => <p key={n} className="pstep-note">{n}</p>)}
        {category.missing.length > 0 && <details className="pstep-bench-missing"><summary>아직 없는 값 {category.missing.length}개</summary>
          <ul>{category.missing.map((m) => <li key={m.key}><b>{m.label}</b> — {m.reason}</li>)}</ul>
        </details>}
        <p className="pstep-bench-actions">
          {industryFill && <button type="button" className="pstep-mini is-strong" onClick={industryFill.run}>업종 평균으로 빈칸 채우기 ({industryFill.label})</button>}
          {equipFill && <button type="button" className="pstep-mini" onClick={equipFill}>업종 평균 장비값 넣기 (주방 · 홀)</button>}
        </p>
      </>}
      {bench.ownership.available && <div className="pstep-bench-own" role="group" aria-label="운영 형태별 평균">
        <h4>개인사업 · 가맹점 평균 <small>{bench.ownership.scope}</small></h4>
        <div className="pstep-table"><table>
          <thead><tr><th scope="col">항목</th>{groups.map((g) => <th key={g.key} scope="col" className={g.key === own ? "is-on" : undefined}
            aria-current={g.key === own ? "true" : undefined}>{g.label}<small> {g.n.toLocaleString("ko-KR")}곳</small></th>)}</tr></thead>
          <tbody>{OWN_KEYS.filter((k) => groups[0]?.values.some((v) => v.key === k)).map((k) => (
            <tr key={k}><th scope="row">{groups[0].values.find((v) => v.key === k)!.label}</th>
              {groups.map((g) => <td key={g.key} className={g.key === own ? "is-on" : undefined}>{cell(g, k)}</td>)}</tr>))}</tbody>
        </table></div>
        <p className="pstep-foot">{groups.map((g) => `${g.label} = ${g.detail}`).join(" · ")}. {bench.ownership.note}</p>
        {ownershipFill && <button type="button" className="pstep-mini" onClick={ownershipFill.run}>{ownLabel} 평균으로 빈칸 채우기 ({ownershipFill.label})</button>}
      </div>}
      <p className="pstep-foot">{bench.note} 출처: {Object.values(bench.sources).map((s, i) => <span key={s.url}>{i > 0 && " · "}<a href={s.url} target="_blank" rel="noreferrer">{s.org} {s.title}</a> ({s.geography} · {s.period} · {s.population})</span>)}</p>
    </div>
  );
}
