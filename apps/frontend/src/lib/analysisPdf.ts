import { jsPDF } from "jspdf";
import regularUrl from "pretendard/dist/public/static/alternative/Pretendard-Regular.ttf?url";

/** 로컬 배포 폰트를 포함해 한글을 검색·복사할 수 있는 A4 PDF를 만든다. 외부 전송은 없다. */
export async function createAnalysisPdf(article: HTMLElement): Promise<jsPDF> {
  const response = await fetch(regularUrl);
  if (!response.ok) throw new Error("보고서 글꼴을 불러오지 못했습니다.");
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  const doc = new jsPDF({ unit: "mm", format: "a4", compress: true, putOnlyUsedFonts: true });
  doc.addFileToVFS("Pretendard.ttf", btoa(binary));
  doc.addFont("Pretendard.ttf", "Pretendard", "normal");
  doc.setFont("Pretendard");
  doc.setProperties({ title: "PlaceOS 상권 분석 보고서", author: "PlaceOS" });
  let y = 22;
  const nextPage = () => { doc.addPage(); y = 22; };
  const blocks = article.querySelectorAll("h1,h2,h3,h4,p,li,dt,dd,pre");
  for (const block of blocks) {
    // 중첩 목록의 글자를 부모·자식에서 두 번 출력하지 않는다.
    if (block.tagName === "LI" && block.querySelector("p,li")) continue;
    // 항목 이름과 값을 함께 출력해 페이지 경계에서 이름만 남지 않게 한다.
    if (block.tagName === "DD" && block.previousElementSibling?.tagName === "DT") continue;
    const definition = block.tagName === "DT" && block.nextElementSibling?.tagName === "DD" ? block.nextElementSibling : null;
    const text = `${block.textContent ?? ""}${definition ? `: ${definition.textContent ?? ""}` : ""}`.trim();
    if (!text) continue;
    const heading = /^H[1-4]$/.test(block.tagName);
    const size = block.tagName === "H1" ? 20 : heading ? 13 : 10;
    const lineHeight = size * 0.3528 * 1.6;
    doc.setFontSize(size);
    const lines = doc.splitTextToSize(text, 174) as string[];
    if (y + lineHeight * (heading ? Math.min(lines.length + 2, 5) : 1) > 272) nextPage();
    if (heading) y += 3;
    doc.setTextColor(heading ? "#29334e" : "#303846");
    for (const line of lines) {
      if (y + lineHeight > 275) nextPage();
      doc.text(line, 18, y);
      y += lineHeight;
    }
    y += heading ? 3 : 2;
  }
  const count = doc.getNumberOfPages();
  for (let page = 1; page <= count; page++) {
    doc.setPage(page); doc.setFontSize(9); doc.setTextColor("#657084");
    doc.text(`PlaceOS · 상권 분석 보고서 | ${page} / ${count}`, 18, 286);
  }
  return doc;
}

export async function downloadAnalysisPdf(article: HTMLElement): Promise<void> {
  const pdf = await createAnalysisPdf(article);
  pdf.save("PlaceOS-상권분석보고서.pdf");
}
