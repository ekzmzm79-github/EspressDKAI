// 표시·접힘은 페이지를 연 시점의 KST 날짜로 계산한다.
// 테스트용으로 ?today=YYYY-MM-DD 를 붙이면 그 날짜로 계산한다.
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("briefing-data").textContent);
  const app = document.getElementById("app");
  const modalRoot = document.getElementById("detail-modal");

  const DAY_MS = 86400000;
  const LLM_DAYS = 7;
  const URGENT_DAYS = 3;
  const STALE_DAYS = 2; // 헤드라인이 이보다 오래되면 첫 화면을 줄이고 "새 소식 없음"을 알린다
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
      else if (k === "onclick") node.addEventListener("click", v);
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

  // ---------- 상세 모달 (카드 높이 늘어남 방지 + 포커스 가두기) ----------

  let lastTrigger = null;

  function buildDetailContent(item) {
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

    return el("div", { class: "more-body" },
      facts,
      el("p", {}, item.detail),
      el("ul", { class: "sources" }, item.sources.map((s) =>
        el("li", {}, el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" }, s.title), ` · ${s.published}`))),
      el("p", { class: "note" }, verification));
  }

  function closeModal() {
    if (!modalRoot || modalRoot.hidden) return;
    modalRoot.classList.remove("is-open");
    modalRoot.setAttribute("aria-hidden", "true");
    modalRoot.hidden = true;
    modalRoot.innerHTML = "";
    document.documentElement.classList.remove("modal-open");
    if (lastTrigger) {
      lastTrigger.focus();
      lastTrigger = null;
    }
  }

  function openModal(item, triggerEl) {
    if (!modalRoot) return;
    lastTrigger = triggerEl || document.activeElement;
    const kicker = item.section === "llm"
      ? `${orgOf(item)} · ${shortDate(item.sources[0].published)}`
      : `${item.hiring.company} · ${item.hiring.type} (~${shortDate(item.hiring.deadline)})`;

    const closeBtn = el("button", {
      type: "button",
      class: "modal-close",
      "aria-label": "닫기",
      onclick: closeModal,
    }, "✕");

    const sheet = el("div", {
      class: "modal-sheet",
      role: "dialog",
      "aria-modal": "true",
      "aria-labelledby": "modal-item-title",
    },
    el("div", { class: "modal-top" },
      el("div", {},
        el("p", { class: "modal-kicker" }, kicker),
        el("h3", { class: "modal-title", id: "modal-item-title" }, item.title)),
      closeBtn),
    points(item),
    buildDetailContent(item));

    modalRoot.innerHTML = "";
    modalRoot.append(sheet);
    modalRoot.hidden = false;
    modalRoot.setAttribute("aria-hidden", "false");
    document.documentElement.classList.add("modal-open");
    requestAnimationFrame(() => {
      modalRoot.classList.add("is-open");
      closeBtn.focus();
    });
  }

  if (modalRoot) {
    modalRoot.addEventListener("click", (e) => {
      if (e.target === modalRoot) closeModal();
    });
    window.addEventListener("keydown", (e) => {
      if (modalRoot.hidden) return;
      if (e.key === "Escape") {
        closeModal();
        return;
      }
      if (e.key !== "Tab") return;
      const focusable = [...modalRoot.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!modalRoot.contains(document.activeElement)) {
        e.preventDefault();
        first.focus();
      } else if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
  }

  // ---------- 공통 조각 ----------

  function points(item) {
    return el("ul", { class: "points" }, item.card.map((line) => el("li", {}, line)));
  }

  function detailTrigger(item) {
    const btn = el("button", {
      type: "button",
      class: "detail-btn",
      onclick: (e) => openModal(item, e.currentTarget),
    }, `자세히 · 원문 ${item.sources.length} ↗`);
    return el("div", { class: "card-actions" }, btn);
  }

  function sectionHead(id, kicker, title, countText, extra) {
    return el("div", { class: "section-head" },
      el("div", { class: "title" },
        el("p", { class: "section-kicker" }, kicker),
        el("div", { class: "section-title-row" },
          el("h2", { id: `${id}-title` }, title),
          el("p", { class: "count" }, countText))),
      extra);
  }

  // ---------- 첫 화면: 시선을 사로잡는 Hero Stage ----------

  function heroCoffeeEmblem() {
    const ns = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("class", "hero-coffee-svg");
    s.setAttribute("viewBox", "0 0 64 76");
    s.setAttribute("fill", "none");
    s.setAttribute("aria-hidden", "true");

    s.innerHTML = `
      <defs>
        <linearGradient id="crema-disc" x1="12" y1="20" x2="52" y2="68" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#f7d4a8" />
          <stop offset="100%" stop-color="#e0a668" />
        </linearGradient>
        <linearGradient id="steam-grad" x1="32" y1="2" x2="32" y2="28" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#f7d4a8" stop-opacity="0" />
          <stop offset="45%" stop-color="#f7d4a8" stop-opacity="0.9" />
          <stop offset="100%" stop-color="#e8b57a" stop-opacity="0.2" />
        </linearGradient>
      </defs>
      <!-- 모락모락 피어오르는 커피 김 3줄기 -->
      <g class="steam-group">
        <path class="steam-wisp wisp-1" d="M24 26 C21 20, 27 15, 24 8" stroke="url(#steam-grad)" stroke-width="2.2" stroke-linecap="round" />
        <path class="steam-wisp wisp-2" d="M32 24 C29 17, 35 11, 32 3" stroke="url(#steam-grad)" stroke-width="2.4" stroke-linecap="round" />
        <path class="steam-wisp wisp-3" d="M40 26 C37 20, 43 15, 40 8" stroke="url(#steam-grad)" stroke-width="2.2" stroke-linecap="round" />
      </g>
      <!-- 반전된 크레마 골드 메달리온 -->
      <circle class="emblem-disc" cx="32" cy="48" r="22" fill="url(#crema-disc)" />
      <!-- 다크 에스프레소 잔 아이콘 (색상 반전) -->
      <g stroke="#120d0a" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 41h17v6.5a6.5 6.5 0 0 1-6.5 6.5h-4a6.5 6.5 0 0 1-6.5-6.5z" fill="#120d0a" fill-opacity="0.14" />
        <path d="M38 43h2.2a3.2 3.2 0 0 1 0 6.4H38" />
        <path d="M20 57.5h19" />
      </g>
    `;
    return el("div", { class: "hero-emblem-wrap", "aria-hidden": "true" }, s);
  }

  function heroTopicPills() {
    const previewItems = items
      .filter((i) => {
        const ago = daysBetween(i.date, today);
        if (i.section === "llm") return ago >= 0 && ago < LLM_DAYS;
        if (i.section === "hiring" && i.hiring) return ago >= 0 && daysBetween(today, i.hiring.deadline) >= 0;
        return false;
      })
      .slice(0, 5);
    if (!previewItems.length) return null;

    return el("div", { class: "hero-topics", "aria-label": "오늘의 주요 브리핑 토픽" },
      previewItems.map((item, idx) => {
        const tag = item.section === "llm"
          ? orgOf(item)
          : `D-${Math.max(0, daysBetween(today, item.hiring.deadline))}`;
        const shortTitle = item.title.length > 22 ? `${item.title.slice(0, 22)}…` : item.title;
        return el("a", {
          class: "topic-pill",
          href: `#item-${item.id}`,
          style: `--pill-idx: ${idx}`,
          onclick: (e) => {
            const target = document.getElementById(`item-${item.id}`);
            if (target) {
              e.preventDefault();
              target.scrollIntoView({ behavior: "smooth", block: "center" });
              target.classList.remove("flash-highlight");
              void target.offsetWidth;
              target.classList.add("flash-highlight");
            }
          },
        },
        el("span", { class: "topic-pill-tag" }, tag),
        el("span", { class: "topic-pill-text" }, shortTitle));
      }));
  }

  function heroStage() {
    const latest = data.days[data.days.length - 1];
    if (!latest) return null;

    const headlineItem = latest.items.find((i) => i.id === latest.headline.item_id) || latest.items[0];
    if (!headlineItem) return null;

    const ago = daysBetween(latest.date, today);
    const stale = ago >= STALE_DAYS;
    const badgeLabel = stale
      ? `최근 새 소식이 없습니다 · 마지막 브리핑 ${longDate(latest.date)}`
      : `${longDate(latest.date)} · ${ago > 0 ? `${ago}일 전 헤드라인` : "TODAY'S HEADLINE"}`;
    const leadLine = headlineItem.card && headlineItem.card[0] ? headlineItem.card[0] : "";

    return el("section", { class: `hero-stage${stale ? " is-stale" : ""}`, "aria-label": stale ? "마지막 헤드라인" : "오늘의 한 줄" },
      el("div", { class: "hero-parallax-inner" },
        heroCoffeeEmblem(),
        el("div", { class: "hero-badge-row" },
          el("span", { class: "pulse-dot", "aria-hidden": "true" }),
          el("p", { class: "eyebrow" }, badgeLabel)),
        el("div", { class: "headline" },
          el("h2", { class: "headline-text" }, latest.headline.text),
          leadLine && el("p", { class: "hero-lead" }, leadLine),
          el("div", { class: "hero-actions" },
            el("button", {
              type: "button",
              class: "btn-primary",
              onclick: (e) => openModal({ ...headlineItem, date: latest.date }, e.currentTarget),
            }, "헤드라인 브리핑 열기 ↗"),
            el("a", { class: "btn-secondary", href: "#showcase-deck" }, "전체 브리핑 탐색 ↓")),
          !stale && heroTopicPills())),
      el("div", { class: "scroll-cue", "aria-hidden": "true" },
        el("span", { class: "scroll-cue-label" }, "SCROLL TO EXPAND"),
        el("span", { class: "scroll-cue-line" },
          el("span", { class: "scroll-cue-drop" }))));
  }

  // ---------- LLM: 넘기는 카드 + 도트 인디케이터 ----------

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
        sectionHead("llm", "GLOBAL AI LABS", title, ""),
        el("p", { class: "empty" }, "최근 7일간 새 소식 없음"));
    }

    const slides = rows.map(({ item, ago }, n) => el("article", {
      class: `slide reveal-card${ago > 0 ? " past" : ""}`,
      id: `item-${item.id}`,
      "data-section": "llm",
      "data-state": ago > 0 ? `${ago}일 전` : "오늘",
    },
    el("div", { class: "slide-top" },
      el("div", { class: "slide-meta" },
        el("p", { class: "org-pill" }, `${orgOf(item)} · ${shortDate(item.sources[0].published)}`),
        el("p", {}, ago > 0
          ? el("span", { class: "badge" }, `${ago}일 전`)
          : `${String(n + 1).padStart(2, "0")} / ${String(rows.length).padStart(2, "0")}`)),
      el("h3", {}, item.title)),
    el("div", { class: "slide-body" }, points(item), detailTrigger(item))));

    const rail = el("div", { class: "rail", tabindex: "0", "aria-label": `${title} 카드, 옆으로 넘기기` }, slides);

    const dots = rows.map((_, idx) => el("button", {
      type: "button",
      class: `rail-dot${idx === 0 ? " active" : ""}`,
      "aria-label": `${idx + 1}번째 카드로 이동`,
      onclick: () => {
        const target = slides[idx];
        if (target) rail.scrollTo({ left: target.offsetLeft - rail.offsetLeft, behavior: "smooth" });
      },
    }));

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
      const slide = slides[0];
      if (slide) {
        const gap = parseFloat(getComputedStyle(rail).columnGap) || 14;
        const idx = Math.min(rows.length - 1, Math.max(0, Math.round(rail.scrollLeft / (slide.offsetWidth + gap))));
        dots.forEach((d, i) => {
          d.classList.toggle("active", i === idx);
          if (i === idx) d.setAttribute("aria-current", "true");
          else d.removeAttribute("aria-current");
        });
      }
    };

    prev.addEventListener("click", () => step(-1));
    next.addEventListener("click", () => step(1));
    rail.addEventListener("scroll", sync, { passive: true });
    window.addEventListener("resize", sync);
    requestAnimationFrame(sync);

    const countText = todayCount ? `오늘 ${todayCount}건 · 최근 7일 ${rows.length}건` : `최근 7일 ${rows.length}건`;
    return el("section", { class: "section", id: "section-llm", "aria-labelledby": "llm-title" },
      sectionHead("llm", "GLOBAL AI LABS", title, countText, el("div", { class: "nav-buttons" }, prev, next)),
      rail,
      rows.length > 1 && el("div", { class: "rail-footer" },
        el("div", { class: "rail-dots", role: "group", "aria-label": "카드 순서" }, dots),
        el("p", { class: "swipe-hint" }, `${rows.length}장의 카드 · 좌우로 스와이프`)));
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
        sectionHead("hiring", "OPPORTUNITIES & HACKATHONS", title, ""),
        el("p", { class: "empty" }, "진행 중인 채용·해커톤 소식 없음"));
    }

    const list = el("div", { class: "deadlines" }, rows.map(({ item, left }) => {
      const isNew = item.date === today;
      const urgent = left <= URGENT_DAYS;
      const state = isNew ? "신규" : urgent ? "마감 임박" : "진행 중";
      return el("article", {
        class: `job reveal-card${urgent ? " urgent" : ""}`,
        id: `item-${item.id}`,
        "data-section": "hiring",
        "data-state": state,
      },
      el("div", { class: "dday" },
        el("span", { "aria-hidden": "true" }, urgent ? "임박" : "마감"),
        el("strong", { "aria-hidden": "true" }, left === 0 ? "D-DAY" : `D-${left}`),
        el("span", { class: "sr-only" }, left === 0 ? "오늘 마감" : `마감까지 ${left}일`)),
      el("div", { class: "job-body" },
        el("p", { class: "job-meta" },
          el("span", { class: `state-pill${isNew ? " new" : urgent ? " soon" : ""}` }, state),
          el("span", {}, `${item.hiring.company} · ${item.hiring.type} · ${shortDate(item.hiring.deadline)} 마감`)),
        el("h3", {}, item.title),
        points(item),
        detailTrigger(item)));
    }));

    return el("section", { class: "section", id: "section-hiring", "aria-labelledby": "hiring-title" },
      sectionHead("hiring", "OPPORTUNITIES & HACKATHONS", title, `마감 순 · 진행 중 ${rows.length}건`),
      list);
  }

  // ---------- 하단 파이프라인 지표 (첫 화면에서 하단으로 분리) ----------

  function telemetrySection() {
    const run = data.last_run;
    if (!run) return null;
    const latest = data.days[data.days.length - 1];
    const todayCount = latest && latest.date === today ? latest.items.length : 0;

    return el("section", { class: "telemetry-section reveal-card", id: "section-telemetry", "aria-label": "실행 지표" },
      el("div", { class: "telemetry-head" },
        el("div", {},
          el("p", { class: "section-kicker" }, "AUTONOMOUS PIPELINE TELEMETRY"),
          el("h2", {}, "오늘의 AI 수집·검증 파이프라인 지표")),
        el("p", { class: "telemetry-sub" }, "AI가 원문과 대조해 검증하고, 사람이 승인한 뒤 공개")),
      el("dl", { class: "stats" },
        [["오늘 공개", `${todayCount}건`], ["수집 후보", `${run.candidates}건`],
          ["검증 수정", `${run.verification_edits}곳`], ["마지막 실행", shortDate(run.date)]]
          .map(([k, v]) => el("div", {}, el("dt", {}, k), el("dd", {}, v)))));
  }

  // ---------- 스크롤 연동 스케일업 & 인터랙티브 배경 ----------

  function initScrollInteractions(heroEl, showcaseEl) {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const revealCards = document.querySelectorAll(".reveal-card");

    revealCards.forEach((c, idx) => {
      c.style.setProperty("--stagger-idx", String(idx % 4));
      c.addEventListener("pointermove", (e) => {
        const r = c.getBoundingClientRect();
        c.style.setProperty("--card-x", `${(e.clientX - r.left).toFixed(0)}px`);
        c.style.setProperty("--card-y", `${(e.clientY - r.top).toFixed(0)}px`);
      }, { passive: true });
    });

    if (reduced) {
      revealCards.forEach((c) => c.classList.add("is-visible"));
      if (showcaseEl) {
        showcaseEl.style.setProperty("--deck-scale", "1");
        showcaseEl.style.setProperty("--deck-y", "0px");
        showcaseEl.style.setProperty("--deck-rx", "0deg");
      }
      return;
    }

    // 교차 원근감(Cross-Scale Parallax): 히어로는 뒤로 물러나고 쇼케이스는 0.74 → 1.00으로 웅장하게 확대
    const updateScrollStage = () => {
      const vh = window.innerHeight || 800;
      const sy = window.scrollY || window.pageYOffset || 0;

      if (heroEl) {
        const heroProgress = Math.min(1, Math.max(0, sy / (vh * 0.68)));
        const hScale = 1 - heroProgress * 0.15;
        const hOpacity = 1 - heroProgress * 0.85;
        const hY = heroProgress * 64;
        heroEl.style.setProperty("--hero-scale", hScale.toFixed(4));
        heroEl.style.setProperty("--hero-opacity", hOpacity.toFixed(4));
        heroEl.style.setProperty("--hero-y", `${hY.toFixed(1)}px`);
      }

      if (showcaseEl) {
        const rect = showcaseEl.getBoundingClientRect();
        // 화면 하단 끝(vh * 0.96)에서 화면 상단(vh * 0.20)으로 올라오는 동안 0 → 1 진행
        const start = vh * 0.96;
        const end = vh * 0.20;
        const raw = (start - rect.top) / (start - end);
        const progress = Math.min(1, Math.max(0, raw));
        // Ease-out 곡선으로 스크롤 시 확 커지는 체감 극대화
        const eased = 1 - Math.pow(1 - progress, 2.2);
        const scale = 0.74 + 0.26 * eased;
        const y = (1 - eased) * 72;
        const rx = (1 - eased) * 9.5;
        const glow = 0.1 + eased * 0.35;
        showcaseEl.style.setProperty("--deck-scale", scale.toFixed(4));
        showcaseEl.style.setProperty("--deck-y", `${y.toFixed(1)}px`);
        showcaseEl.style.setProperty("--deck-rx", `${rx.toFixed(2)}deg`);
        showcaseEl.style.setProperty("--deck-glow", glow.toFixed(3));
      }
    };

    window.addEventListener("scroll", updateScrollStage, { passive: true });
    window.addEventListener("resize", updateScrollStage);
    requestAnimationFrame(updateScrollStage);

    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
          }
        }
      }, { threshold: 0.12, rootMargin: "0px 0px -24px 0px" });
      revealCards.forEach((c) => io.observe(c));
    } else {
      revealCards.forEach((c) => c.classList.add("is-visible"));
    }
  }

  function initAmbientCanvas() {
    const canvas = document.getElementById("bg-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let running = false;
    let width = 0;
    let height = 0;
    let dots = [];
    const mouse = { x: -1000, y: -1000, active: false };

    function buildGrid() {
      width = window.innerWidth;
      height = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const spacing = width < 720 ? 44 : 50;
      dots = [];
      for (let x = spacing / 2; x < width; x += spacing) {
        for (let y = spacing / 2; y < height; y += spacing) {
          dots.push({ ox: x, oy: y, x, y, phase: (x * 0.016) + (y * 0.016) });
        }
      }
    }

    function start() {
      if (running || reduced || document.hidden) return;
      running = true;
      requestAnimationFrame(draw);
    }

    window.addEventListener("pointermove", (e) => {
      if (e.pointerType !== "mouse") return;
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.active = true;
      document.documentElement.style.setProperty("--mouse-x", `${e.clientX}px`);
      document.documentElement.style.setProperty("--mouse-y", `${e.clientY}px`);
      start();
    }, { passive: true });

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) start();
    });

    window.addEventListener("pointerleave", () => {
      mouse.active = false;
    });

    window.addEventListener("resize", () => {
      buildGrid();
      if (!running) requestAnimationFrame(draw);
    });
    buildGrid();

    function draw(t) {
      ctx.clearRect(0, 0, width, height);
      const time = (t || 0) * 0.0014;
      const radius = 210;

      for (let i = 0; i < dots.length; i++) {
        const d = dots[i];
        let tx = d.ox + Math.sin(time + d.phase) * 2.8;
        let ty = d.oy + Math.cos(time + d.phase) * 2.8;
        let alpha = 0.18;
        let size = 1.4;

        if (mouse.active) {
          const dx = tx - mouse.x;
          const dy = ty - mouse.y;
          const dist = Math.hypot(dx, dy);
          if (dist < radius && dist > 0.1) {
            const force = (1 - dist / radius);
            tx += (dx / dist) * force * 20;
            ty += (dy / dist) * force * 20;
            alpha = 0.18 + force * 0.65;
            size = 1.4 + force * 1.9;
          }
        }

        d.x += (tx - d.x) * 0.18;
        d.y += (ty - d.y) * 0.18;

        ctx.beginPath();
        ctx.arc(d.x, d.y, size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(232, 181, 122, ${alpha.toFixed(3)})`;
        ctx.fill();
      }

      if (!reduced && !document.hidden) {
        requestAnimationFrame(draw);
      } else {
        running = false;
      }
    }

    if (reduced) {
      requestAnimationFrame(draw);
    } else {
      start();
    }
  }

  // ---------- 그리기 ----------

  document.getElementById("today-label").textContent = `${longDate(today)} · 아침 AI 브리핑`;

  if (!items.length) {
    app.append(el("p", { class: "empty" }, "아직 공개된 소식이 없습니다."));
  } else {
    const heroEl = heroStage();
    const showcaseEl = el("div", { class: "showcase-shell", id: "showcase-deck" },
      llmSection(),
      hiringSection());
    const telemetryEl = telemetrySection();

    app.append(heroEl || "", showcaseEl, telemetryEl || "");
    initScrollInteractions(heroEl, showcaseEl);
  }

  initAmbientCanvas();

  const run = data.last_run;
  document.getElementById("run-info").append(
    el("p", {}, "AI가 수집·검증하고 사람이 승인해 공개합니다"),
    el("p", {}, run
      ? `마지막 실행 ${shortDate(run.date)} · 수집 ${run.candidates} · 통과 ${run.passed} · 검증 수정 ${run.verification_edits}`
      : "아직 실행 기록이 없습니다."));
})();
