import "./EvidenceBadge.css";

export type Evidence = "실측" | "통계" | "추정" | "사용자 입력" | "계산" | "참고 지수";

/** 숫자마다 붙는 근거 등급. 값이 어디서 왔는지를 칸마다 밝힌다. */
export default function EvidenceBadge({ kind }: { kind: Evidence }) {
  return <span className={`evid evid-${kind === "실측" ? "real" : kind === "통계" ? "stat" : "soft"}`}>{kind}</span>;
}
