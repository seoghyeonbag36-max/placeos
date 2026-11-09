import { KEYWORD_EFFECT, KEYWORD_GROUPS } from "@/lib/interiorLayout";

/** 공간 구성 키워드(2026-11-09 사용자 지정 15개 + 더한 15개 · 네 갈래) — 누르면 3D 배치가 그 키워드에 맞게 다시 놓인다. */
export default function InteriorKeywordChips({ value, onChange }: { value: readonly string[]; onChange: (next: string[]) => void }) {
  const toggle = (k: string) => onChange(value.includes(k) ? value.filter((x) => x !== k) : [...value, k]);
  return (
    <div className="interior-kw">
      <div role="group" aria-label="공간 구성 키워드">
        {KEYWORD_GROUPS.map((g) => (
          <div key={g.name} className="interior-kw-group">
            <span>{g.name}</span>
            <div className="interior-kw-chips">
              {g.keywords.map((k) => (
                <button type="button" key={k} aria-pressed={value.includes(k)} title={KEYWORD_EFFECT[k]} onClick={() => toggle(k)}>#{k}</button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="interior-kw-picked" role="status">
        {value.length ? <>고른 키워드: {value.map((k) => `#${k}`).join(" ")} <button type="button" onClick={() => onChange([])}>모두 끄기</button></>
          : "키워드를 누르면 3D 디지털 트윈이 가구 · 의자 · 인테리어 물품을 그 키워드에 맞게 다시 놓습니다."}
      </p>
      {value.length > 0 && <ul className="interior-kw-effects">{value.map((k) => <li key={k}><b>#{k}</b> {KEYWORD_EFFECT[k as keyof typeof KEYWORD_EFFECT] ?? ""}</li>)}</ul>}
    </div>
  );
}
