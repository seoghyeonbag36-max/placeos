import type { FloorVacancyUnit } from "@/lib/api";
import { aprText, buildingAge, floorUseCheck } from "@/lib/founderChecks";

/**
 * Page 건물 상세 — 층 용도로 본 음식점 영업(N2) · 건물 연식(N8) (2026-11-12 사용자 요청).
 * 근거는 건축물대장 기재값뿐이다(층별개요 용도 · 표제부 사용승인일). 지금 실제 용도와 다를 수 있고, 영업신고 가능 여부는
 * 관할 구청이 정한다 — 화면은 늘 그렇게 적는다.
 */
export default function FloorUseBox({ units, loading, missing }: { units: FloorVacancyUnit[] | null; loading: boolean; missing: boolean }) {
  const rows = units ?? [];
  const apr = rows.find((u) => u.use_apr)?.use_apr ?? null;
  const age = buildingAge(apr);
  const shared = rows.some((u) => u.bldgs_on_pnu > 1);
  return (
    <div className="b-usebox" role="region" aria-label="층 용도로 본 영업">
      <div className="b-rec-h">층 용도로 본 영업<span className="b-rent-badge">대장 기재</span></div>
      {loading ? <div className="b-rec-note">층 용도를 불러오는 중…</div>
        : missing ? <div className="b-rec-note">이 상권은 층 용도 자료가 없습니다.</div>
        : <>
          {age != null && apr && <div className="b-age"><b>{age}년 된 건물</b> · 사용승인 {aprText(apr)}
            {age >= 30 && <small> — 오래된 건물은 전기 증설 · 배관 · 방수 공사가 더 들 수 있어 인테리어 견적에 넣어 확인하세요.</small>}</div>}
          {rows.length === 0 ? <div className="b-rec-note">이 건물에는 층 용도를 붙일 빈 층이 없습니다.</div> : (
            <ul className="b-uselist">
              {rows.map((u) => {
                const c = floorUseCheck(u.purps, u.area_m2);
                return <li key={u.id} className={`is-${c.group}`}>
                  <span className="b-use-floor">{u.floor_label}</span>
                  <span className="b-use-purps">{u.purps || "용도 미상"}</span>
                  <span className={`b-use-badge is-${c.group}`}>{c.badge}</span>
                  <small>{c.food}</small>
                </li>;
              })}
            </ul>)}
          <div className="b-rec-note">대장 기재 용도는 지금 실제 용도와 다를 수 있어요. 정화조 · 주차 같은 건축기준과 영업신고는 관할 구청(건축과 · 위생과)에서 확인하세요.
            {shared && " 같은 지번에 건물이 여럿이라 어느 동의 층인지는 모릅니다."}</div>
        </>}
    </div>
  );
}
