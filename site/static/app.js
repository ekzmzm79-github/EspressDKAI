// 표시·접힘은 페이지를 연 시점의 KST 날짜로 계산한다.
// 테스트용으로 ?today=YYYY-MM-DD 를 붙이면 그 날짜로 계산한다.
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("briefing-data").textContent);
  const app = document.getElementById("app");

  const DAY_MS = 86400000;
  const LLM_DAYS = 7;
  const URGENT_DAYS = 3;

  function todayKst() {
    const param = new URLSearchParams(location.search).get("today");
    if (param && /^\d{4}-\d{2}-\d{2}$/.test(param)) return param;
    return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
  }

  function daysBetween(from, to) {
    return Math.round((Date.parse(to) - Date.parse(from)) / DAY_MS);
  }

  function shortDate(iso) {
    const [, m, d] = iso.split("-");
    return `${Number(m)}/${Number(d)}`;
  }

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === "class") node.className = v;
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) {
      if (c == null || c === false) continue;
      node.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return node;
  }

  const today = todayKst();
  const items = data.days.flatMap((day) => day.items.map((item) => ({ ...item, date: day.date })));

  // 항목별 표시 규칙 (기획서 "섹션별 표시 규칙")
  function llmState(item) {
    const ago = daysBetween(item.date, today);
    if (ago < 0 || ago >= LLM_DAYS) return null;
    return ago === 0 ? { badge: null, open: true } : { badge: `${ago}일 전 소식`, open: false };
  }

  function hiringState(item) {
    const left = daysBetween(today, item.hiring.deadline);
    if (left < 0 || daysBetween(item.date, today) < 0) return null;
    if (item.date === today) return { badge: "신규", open: true, tone: "new" };
    if (left <= URGENT_DAYS) return { badge: `마감 임박 · ${shortDate(item.hiring.deadline)}`, open: true, tone: "urgent" };
    return { badge: `진행 중 · 마감 ${shortDate(item.hiring.deadline)}`, open: false };
  }

  function sourceLinks(item) {
    return el("ul", { class: "sources" },
      item.sources.map((s) =>
        el("li", {}, el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" }, s.title),
          el("span", { class: "muted" }, ` · ${s.published}`))));
  }

  function hiringFacts(h) {
    const rows = [
      ["기업", h.company], ["유형", h.type], ["대상", h.targets.join("·")], ["자격", h.eligibility],
      ["접수", h.apply_start ? `${h.apply_start} ~ ${h.deadline}` : `~ ${h.deadline}`], ["혜택", h.benefit],
    ].filter(([, v]) => v);
    return el("dl", { class: "facts" }, rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
  }

  function card(item, state) {
    const section = data.sections[item.section];
    const verification = item.verification.status === "fixed"
      ? `검증 단계에서 ${item.verification.edits}곳 수정${item.verification.note ? ` (${item.verification.note})` : ""}`
      : "검증 통과";
    return el("article", { class: "card", id: `item-${item.id}`, "data-section": item.section },
      el("details", { class: "fold", open: state.open },
        el("summary", {},
          el("span", { class: "tag" }, section.title),
          state.badge && el("span", { class: `badge ${state.tone || ""}` }, state.badge),
          el("h3", {}, item.title)),
        el("ul", { class: "points" }, item.card.map((line) => el("li", {}, line))),
        el("details", { class: "detail" },
          el("summary", {}, "자세히"),
          item.hiring && hiringFacts(item.hiring),
          el("p", {}, item.detail),
          sourceLinks(item),
          el("p", { class: "muted small" }, verification))));
  }

  function headline() {
    const latest = data.days[data.days.length - 1];
    if (!latest || !latest.items.some((i) => i.id === latest.headline.item_id)) return null;
    const ago = daysBetween(latest.date, today);
    if (ago < 0) return null;
    return el("section", { class: "headline" },
      el("details", { open: ago === 0 },
        el("summary", {},
          el("span", { class: "label" }, "오늘의 한 줄"),
          ago > 0 && el("span", { class: "badge" }, `${ago}일 전`)),
        el("a", { href: `#item-${latest.headline.item_id}` }, latest.headline.text)));
  }

  function section(id, title, rows, emptyText) {
    rows.sort((a, b) => (b.state.open - a.state.open) || b.item.date.localeCompare(a.item.date));
    return el("section", { class: "section", id: `section-${id}` },
      el("h2", {}, title),
      rows.length
        ? el("div", { class: "cards" }, rows.map((r) => card(r.item, r.state)))
        : el("p", { class: "empty" }, emptyText));
  }

  function rowsFor(sectionId, stateFn) {
    return items
      .filter((i) => i.section === sectionId)
      .map((item) => ({ item, state: stateFn(item) }))
      .filter((r) => r.state);
  }

  if (!items.length) {
    app.append(el("p", { class: "empty" }, "아직 공개된 소식이 없습니다."));
  } else {
    app.append(
      headline() || "",
      section("llm", data.sections.llm.title, rowsFor("llm", llmState), "최근 7일간 새 소식 없음"),
      section("hiring", data.sections.hiring.title, rowsFor("hiring", hiringState), "진행 중인 채용·해커톤 소식 없음"));
  }

  const run = data.last_run;
  document.getElementById("run-info").append(
    run
      ? `마지막 실행 ${run.date} · 수집 ${run.candidates} · 통과 ${run.passed} · 검증 수정 ${run.verification_edits}`
      : "아직 실행 기록이 없습니다.");
})();
