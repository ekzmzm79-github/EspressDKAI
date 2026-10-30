// 표시·접힘은 페이지를 연 시점의 KST 날짜로 계산한다.
// 테스트용으로 ?today=YYYY-MM-DD 를 붙이면 그 날짜로 계산한다.
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("briefing-data").textContent);
  const app = document.getElementById("app");

  const DAY_MS = 86400000;
  const LLM_DAYS = 7;
  const URGENT_DAYS = 3;
  const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

  // 원문 주소 → 회사 이름 (LLM 카드 머리글)
  const ORGS = [
    [/(^|\.)(openai\.com|chatgpt\.com)$/, "OpenAI"],
    [/(^|\.)(anthropic\.com|claude\.com|claude\.ai)$/, "Anthropic"],
    [/(^|\.)(google|deepmind\.google|blog\.google|gemini\.google|googleblog\.com)$/, "Google"],
    [/(^|\.)github\.com$|githubusercontent\.com$/, "GitHub"],
  ];

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

  function longDate(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
    return `${m}월 ${d}일 ${weekday}요일`;
  }

  function orgOf(item) {
    try {
      const host = new URL(item.sources[0].url).hostname;
      const hit = ORGS.find(([re]) => re.test(host));
      return hit ? hit[1] : host.replace(/^www\./, "");
    } catch (e) {
      return "";
    }
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

  function svg(path) {
    const ns = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("fill", "none");
    s.setAttribute("stroke", "currentColor");
    s.setAttribute("stroke-width", "2");
    s.setAttribute("aria-hidden", "true");
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", path);
    s.append(p);
    return s;
  }

  const today = todayKst();
  const items = data.days.flatMap((day) => day.items.map((item) => ({ ...item, date: day.date })));

  // ---------- 공통 조각 ----------

  function points(item) {
    return el("ul", { class: "points" }, item.card.map((line) => el("li", {}, line)));
  }

  function more(item) {
    const v = item.verification;
    const verification = v.status === "fixed"
      ? `검증 단계에서 ${v.edits}곳 수정${v.note ? ` · ${v.note}` : ""}`
      : "검증 통과";
    const h = item.hiring;
    const facts = h && el("dl", { class: "facts" },
      [["주최", h.company], ["유형", h.type], ["대상", h.targets.join("·")], ["자격", h.eligibility],
        ["접수", h.apply_start ? `${h.apply_start} ~ ${h.deadline}` : `~ ${h.deadline}`], ["혜택", h.benefit]]
        .filter(([, value]) => value)
        .flatMap(([k, value]) => [el("dt", {}, k), el("dd", {}, value)]));
    return el("details", { class: "more" },
      el("summary", {}, `자세히 · 원문 ${item.sources.length}`),
      el("div", { class: "more-body" },
        facts,
        el("p", {}, item.detail),
        el("ul", { class: "sources" }, item.sources.map((s) =>
          el("li", {}, el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" }, s.title), ` · ${s.published}`))),
        el("p", { class: "note" }, verification)));
  }

  function sectionHead(id, title, countText, extra) {
    return el("div", { class: "section-head" },
      el("div", { class: "title" }, el("h2", { id: `${id}-title` }, title), el("p", { class: "count" }, countText)),
      extra);
  }

  // ---------- 오늘의 한 줄 + 실행 지표 ----------

  function hero() {
    const latest = data.days[data.days.length - 1];
    const run = data.last_run;
    const todayCount = latest && latest.date === today ? latest.items.length : 0;
    const parts = [];

    if (latest && latest.items.some((i) => i.id === latest.headline.item_id)) {
      const ago = daysBetween(latest.date, today);
      parts.push(el("section", { class: "headline", "aria-label": "오늘의 한 줄" },
        el("p", { class: "eyebrow" }, `${longDate(latest.date)} · ${ago > 0 ? `${ago}일 전 한 줄` : "오늘의 한 줄"}`),
        el("p", { class: "headline-text" }, latest.headline.text),
        el("a", { href: `#item-${latest.headline.item_id}` }, "카드로 보기 →")));
    }
    if (run) {
      parts.push(el("dl", { class: "stats", "aria-label": "실행 지표" },
        [["오늘 공개", `${todayCount}건`], ["수집 후보", `${run.candidates}건`],
          ["검증 수정", `${run.verification_edits}곳`], ["마지막 실행", shortDate(run.date)]]
          .map(([k, v]) => el("div", {}, el("dt", {}, k), el("dd", {}, v)))));
    }
    return parts.length ? el("div", { class: "hero" }, parts) : null;
  }

  // ---------- LLM: 넘기는 카드 ----------

  function llmSection() {
    const rows = items
      .filter((i) => i.section === "llm")
      .map((item) => ({ item, ago: daysBetween(item.date, today) }))
      .filter((r) => r.ago >= 0 && r.ago < LLM_DAYS)
      .sort((a, b) => a.ago - b.ago || a.item.id.localeCompare(b.item.id));
    const todayCount = rows.filter((r) => r.ago === 0).length;
    const title = data.sections.llm.title;

    if (!rows.length) {
      return el("section", { class: "section", id: "section-llm", "aria-labelledby": "llm-title" },
        sectionHead("llm", title, ""), el("p", { class: "empty" }, "최근 7일간 새 소식 없음"));
    }

    const rail = el("div", { class: "rail", tabindex: "0", "aria-label": `${title} 카드, 옆으로 넘기기` },
      rows.map(({ item, ago }, n) => el("article", {
        class: `slide${ago > 0 ? " past" : ""}`, id: `item-${item.id}`, "data-section": "llm",
        "data-state": ago > 0 ? `${ago}일 전` : "오늘",
      },
      el("div", { class: "slide-top" },
        el("div", { class: "slide-meta" },
          el("p", {}, `${orgOf(item)} · ${shortDate(item.sources[0].published)}`),
          el("p", {}, ago > 0 ? el("span", { class: "badge" }, `${ago}일 전`) : `${String(n + 1).padStart(2, "0")} / ${String(rows.length).padStart(2, "0")}`)),
        el("h3", {}, item.title)),
      el("div", { class: "slide-body" }, points(item), more(item)))));

    const prev = el("button", { type: "button", class: "round", "aria-label": "이전 카드" }, svg("M15 6l-6 6 6 6"));
    const next = el("button", { type: "button", class: "round", "aria-label": "다음 카드" }, svg("M9 6l6 6-6 6"));
    const step = (dir) => {
      const slide = rail.querySelector(".slide");
      const gap = parseFloat(getComputedStyle(rail).columnGap) || 0;
      rail.scrollBy({ left: dir * (slide.offsetWidth + gap), behavior: "smooth" });
    };
    const sync = () => {
      prev.disabled = rail.scrollLeft <= 2;
      next.disabled = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 2;
    };
    prev.addEventListener("click", () => step(-1));
    next.addEventListener("click", () => step(1));
    rail.addEventListener("scroll", sync, { passive: true });
    window.addEventListener("resize", sync);
    requestAnimationFrame(sync);

    const countText = todayCount ? `오늘 ${todayCount}건 · 최근 7일 ${rows.length}건` : `최근 7일 ${rows.length}건`;
    return el("section", { class: "section", id: "section-llm", "aria-labelledby": "llm-title" },
      sectionHead("llm", title, countText, el("div", { class: "nav-buttons" }, prev, next)),
      rail);
  }

  // ---------- 채용·해커톤: 마감 순 ----------

  function hiringSection() {
    const rows = items
      .filter((i) => i.section === "hiring" && daysBetween(i.date, today) >= 0)
      .map((item) => ({ item, left: daysBetween(today, item.hiring.deadline) }))
      .filter((r) => r.left >= 0)
      .sort((a, b) => a.left - b.left || a.item.id.localeCompare(b.item.id));
    const title = data.sections.hiring.title;

    if (!rows.length) {
      return el("section", { class: "section", id: "section-hiring", "aria-labelledby": "hiring-title" },
        sectionHead("hiring", title, ""), el("p", { class: "empty" }, "진행 중인 채용·해커톤 소식 없음"));
    }

    const list = el("div", { class: "deadlines" }, rows.map(({ item, left }) => {
      const isNew = item.date === today;
      const urgent = left <= URGENT_DAYS;
      const state = isNew ? "신규" : urgent ? "마감 임박" : "진행 중";
      return el("article", {
        class: `job${urgent ? " urgent" : ""}`, id: `item-${item.id}`, "data-section": "hiring", "data-state": state,
      },
      el("div", { class: "dday", "aria-label": `마감 ${left === 0 ? "오늘" : `${left}일 남음`}` },
        el("span", { "aria-hidden": "true" }, "마감"),
        el("strong", { "aria-hidden": "true" }, left === 0 ? "D-DAY" : `D-${left}`)),
      el("div", { class: "job-body" },
        el("p", { class: "job-meta" },
          el("span", { class: isNew ? "new" : urgent ? "soon" : "" }, state),
          ` · ${item.hiring.type} · ${shortDate(item.hiring.deadline)} 마감`),
        el("h3", {}, item.title),
        points(item),
        more(item)));
    }));

    return el("section", { class: "section", id: "section-hiring", "aria-labelledby": "hiring-title" },
      sectionHead("hiring", title, `마감 순 · 진행 중 ${rows.length}건`),
      list);
  }

  // ---------- 그리기 ----------

  document.getElementById("today-label").textContent = `${longDate(today)} · 아침 AI 브리핑`;

  if (!items.length) {
    app.append(el("p", { class: "empty" }, "아직 공개된 소식이 없습니다."));
  } else {
    app.append(hero() || "", llmSection(), hiringSection());
  }

  const run = data.last_run;
  document.getElementById("run-info").append(
    el("p", {}, "AI가 수집·검증하고 사람이 승인해 공개합니다"),
    el("p", {}, run
      ? `마지막 실행 ${shortDate(run.date)} · 수집 ${run.candidates} · 통과 ${run.passed} · 검증 수정 ${run.verification_edits}`
      : "아직 실행 기록이 없습니다."));
})();
