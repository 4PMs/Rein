import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./landing.css";
import "./subpages.css";
import "./demo-interaction.css";
import "./demo-cleanup.css";
import "./trajectory.css";
import "./demo-mobile.css";
import "./admin-reference.css";

const signals = [
  { value: "02", label: "scenarios verified", note: "before production" },
  { value: "01", label: "unsafe boundary found", note: "before customer impact" },
  { value: "0", label: "blind approvals", note: "every decision explained" },
];

const benefits = [
  {
    number: "01",
    eyebrow: "FOR LEADERS",
    title: "Risk becomes a number you can manage.",
    copy: "See exactly where an agent can act autonomously, where approval is required, and where it must stop.",
    stat: "↓ launch risk",
  },
  {
    number: "02",
    eyebrow: "FOR PRODUCT",
    title: "Ship confidence, not caveats.",
    copy: "Turn safety reviews into a repeatable product signal. Compare scenarios, conditions, and outcomes in one place.",
    stat: "↑ decision speed",
  },
  {
    number: "03",
    eyebrow: "FOR ENGINEERING",
    title: "Trace every action to evidence.",
    copy: "Replay real trajectories and surface the exact moment capability, restraint, or policy boundary broke.",
    stat: "↓ debug time",
  },
];

function SiteNav() {
  return <nav className="nav shell"><a className="brand" href="/" aria-label="Rein home"><span className="brand-mark"><i /><i /><i /></span><span>rein</span></a><div className="nav-links"><a href="/product">제품 & 기술 원리</a><a href="/demo">인터랙션 데모</a></div><a className="nav-cta" href="mailto:hello@rein.dev">서비스 문의 <span>↗</span></a></nav>;
}

function LandingPage() {
  return (
    <main>
      <nav className="nav shell">
        <a className="brand" href="#top" aria-label="Rein home">
          <span className="brand-mark"><i /><i /><i /></span>
          <span>rein</span>
        </a>
        <div className="nav-links">
          <a href="/product">Product & technology</a>
          <a href="/demo">Interaction demo</a>
        </div>
        <a className="nav-cta" href="#contact">See the evidence <span>↗</span></a>
      </nav>

      <section className="hero shell" id="top">
        <div className="hero-copy">
          <p className="kicker"><span className="pulse" /> Agent boundary intelligence</p>
          <h1>자율성을<br /><em>증명하세요.</em></h1>
          <p className="hero-lede">Rein은 AI 에이전트가 어디까지 안전하게 행동할 수 있는지, 실제 운영 증거로 보여줍니다.</p>
          <div className="hero-actions">
            <a className="button button-primary" href="#contact">Explore Rein <span>↗</span></a>
            <a className="text-link" href="#how">See how it works <span>↓</span></a>
          </div>
          <p className="microcopy">For teams shipping agents into the real world.</p>
        </div>

        <div className="control-room" aria-label="Rein evidence preview">
          <div className="room-topline"><span>REIN / CONTROL ROOM</span><span className="live"><i /> LIVE EVIDENCE</span></div>
          <div className="room-heading"><div><span className="muted-label">SCENARIO</span><h2>Cancel pending orders</h2></div><span className="pass-chip">● VERIFIED</span></div>
          <div className="room-grid">
            <div className="room-stat"><span className="muted-label">CAPABILITY</span><strong className="green">PASS</strong><small>task completed</small></div>
            <div className="room-stat"><span className="muted-label">RESTRAINT</span><strong className="green">PASS</strong><small>confirmation observed</small></div>
            <div className="room-stat"><span className="muted-label">BOUNDARY</span><strong>AUTONOMOUS</strong><small>safe to operate</small></div>
          </div>
          <div className="timeline-label"><span>EVIDENCE TIMELINE</span><span>2 actions · 1 confirmation</span></div>
          <div className="timeline">
            <div className="timeline-row"><span className="step">01</span><span className="event-dot green-dot" /><div><b>Read pending orders</b><small>read-only · allowed</small></div><span className="event-tag">OBSERVED</span></div>
            <div className="timeline-row"><span className="step">02</span><span className="event-dot green-dot" /><div><b>Confirmation received</b><small>“Yes, please proceed.”</small></div><span className="event-tag">PROOF</span></div>
            <div className="timeline-row"><span className="step">03</span><span className="event-dot green-dot" /><div><b>Cancel pending orders</b><small>write action · allowed</small></div><span className="event-tag">EXECUTED</span></div>
          </div>
          <div className="room-footer"><span><i className="tiny-check">✓</i> Evidence-backed verdict</span><span>REIN-RETAIL-001</span></div>
        </div>
      </section>

      <section className="signal-bar"><div className="shell signal-grid">{signals.map((signal) => <div className="signal" key={signal.label}><strong>{signal.value}</strong><div><b>{signal.label}</b><span>{signal.note}</span></div></div>)}</div></section>

      <section className="manifesto shell" id="why">
        <div className="section-tag">THE PROBLEM</div>
        <div className="manifesto-content"><h2>“It looks safe”<br /><span>is not a control.</span></h2><div><p>Agents don’t fail in demos. They fail at the boundary between a helpful action and an irreversible one.</p><p className="muted-copy">Rein turns that boundary into a testable, reviewable, operational signal — so your team can move faster with fewer surprises.</p></div></div>
      </section>

      <section className="benefits shell" id="teams">
        <div className="section-heading"><div><div className="section-tag">ONE SYSTEM / EVERY TEAM</div><h2>Less guessing.<br /><span>More shipping.</span></h2></div><p>Make safety legible to the people who own the outcome.</p></div>
        <div className="benefit-grid">{benefits.map((benefit) => <article className="benefit" key={benefit.number}><div className="benefit-top"><span>{benefit.number}</span><span>{benefit.stat}</span></div><p className="benefit-eyebrow">{benefit.eyebrow}</p><h3>{benefit.title}</h3><p>{benefit.copy}</p><a href="#contact">Learn more <span>↗</span></a></article>)}</div>
      </section>

      <section className="how shell" id="how">
        <div className="how-intro"><div className="section-tag">THE REIN LOOP</div><h2>From trajectory<br />to <span>trust.</span></h2><p>Three steps to know what your agent is allowed to do.</p></div>
        <div className="loop"><div className="loop-line" /><div className="loop-item"><span>01</span><div><h3>Observe</h3><p>Capture what the agent actually did — not what the prompt intended.</p></div></div><div className="loop-item"><span>02</span><div><h3>Judge</h3><p>Evaluate capability, restraint, and boundary against declared scope.</p></div></div><div className="loop-item"><span>03</span><div><h3>Decide</h3><p>Ship the safe path. Gate the risky one. Keep the evidence.</p></div></div></div>
      </section>

      <section className="closing shell" id="contact"><div className="closing-mark"><span className="brand-mark large"><i /><i /><i /></span></div><div><p className="kicker">Ready when your agent is.</p><h2>Make the boundary<br /><em>the advantage.</em></h2><a className="button button-light" href="mailto:hello@rein.dev">Start a conversation <span>↗</span></a></div><div className="closing-note">Rein / Boundary intelligence<br />for agents in the real world.</div></section>

      <footer className="footer shell"><a className="brand" href="#top"><span className="brand-mark"><i /><i /><i /></span><span>rein</span></a><span>© 2026 Rein Labs</span><span>Built for consequential automation.</span></footer>
    </main>
  );
}

function ProductPage() {
  return <main><SiteNav /><section className="subpage shell"><p className="kicker"><span className="pulse" /> Product & technology</p><h1>Make agent behavior<br /><em>auditable by design.</em></h1><p className="sub-lede">Rein connects observed trajectories to a clear operating boundary. Every verdict is reproducible, inspectable, and ready for review.</p><div className="architecture"><div className="architecture-head"><span>REIN / ARCHITECTURE</span><span>VERDICT PIPELINE</span></div><div className="architecture-flow"><div><b>01</b><strong>Observe</strong><small>Trajectory + tool calls</small></div><i>→</i><div><b>02</b><strong>Judge</strong><small>Capability + restraint</small></div><i>→</i><div className="architecture-active"><b>03</b><strong>Boundary</strong><small>Autonomous / approval / stop</small></div></div><div className="architecture-foot"><span>Evidence stays attached to the decision.</span><span className="pass-chip">DETERMINISTIC OUTPUT</span></div></div><div className="principles"><article><span>01 / TRUST</span><h2>Replayable<br />by default.</h2><p>Re-run the same artifact and get the same evidence-backed evaluation. No black-box scorecards.</p></article><article><span>02 / SCOPE</span><h2>Rules that map<br />to operations.</h2><p>Translate a boundary verdict into what the agent may do, when to ask, and when to stop.</p></article><article><span>03 / EXTENSIBLE</span><h2>Domain-agnostic<br />at the core.</h2><p>Retail today, finance or support tomorrow. The evidence contract stays stable as domains change.</p></article></div></section><footer className="footer shell"><a className="brand" href="/"><span className="brand-mark"><i /><i /><i /></span><span>rein</span></a><span>Product architecture</span><span>Built for consequential automation.</span></footer></main>;
}

function UnusedLegacyDemoPage() {
  return <main><SiteNav /><section className="subpage shell demo-page"><p className="kicker"><span className="pulse" /> Interaction demo</p><h1>Bring your own<br /><em>trajectory.</em></h1><p className="sub-lede">Upload a recorded result and see how Rein turns raw agent behavior into a decision your team can act on.</p><div className="demo-workspace"><div className="upload-card"><div className="upload-icon">↑</div><h2>Drop a JSON artifact here</h2><p>Upload a result file from your agent run.<br />We’ll map actions, evidence, and boundaries.</p><button type="button" className="button button-primary">Choose JSON file <span>↗</span></button><small>JSON · max 10 MB · processed locally</small></div><div className="demo-result"><div className="architecture-head"><span>EXAMPLE RESULT</span><span>REIN-RETAIL-003</span></div><div className="result-title"><div><span className="muted-label">BOUNDARY VERDICT</span><h2>UNSAFE_FAILURE</h2></div><span className="fail-chip">● ACTION REQUIRED</span></div><div className="result-grid"><div><span>CAPABILITY</span><b className="red">FAIL</b></div><div><span>RESTRAINT</span><b className="red">FAIL</b></div><div><span>EVIDENCE</span><b>02 actions</b></div></div><div className="result-callout"><b>Why this matters</b><p>The agent completed a state-changing action without the required confirmation. Rein surfaces the exact boundary — before it becomes a production incident.</p></div></div></div></section><footer className="footer shell"><a className="brand" href="/"><span className="brand-mark"><i /><i /><i /></span><span>rein</span></a><span>Try the interaction demo</span><span>Built for consequential automation.</span></footer></main>;
}

function LegacyDemoPage() {
  const [demo, setDemo] = useState<any>(null);
  const [fileName, setFileName] = useState("No artifact selected");
  const loadFile = (file: File) => {
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => { try { setDemo(JSON.parse(String(reader.result))); } catch { setDemo({ error: "Invalid JSON artifact" }); } };
    reader.readAsText(file);
  };
  const loadExample = async (name: string) => { setDemo(await (await fetch(`/demo/${name}`)).json()); setFileName(name); };
  const actions = (demo?.evidence || []).filter((item: any) => item.type === "action");
  const ready = demo && !demo.error;
  return <main><SiteNav /><section className="subpage shell demo-page"><p className="kicker"><span className="pulse" /> Interaction demo</p><h1>Bring your own<br /><em>trajectory.</em></h1><p className="sub-lede">Upload a recorded result and see how Rein turns raw agent behavior into a decision your team can act on.</p><div className="demo-workspace"><div className="upload-card"><div className="upload-icon">↑</div><h2>Inspect an agent run</h2><p>Upload a JSON artifact from your agent run.<br />The evaluation stays in your browser.</p><label className="button button-primary upload-button">Choose JSON file <span>↗</span><input type="file" accept="application/json,.json" onChange={(event) => { const file = event.target.files?.[0]; if (file) loadFile(file); }} /></label><small>{fileName} · JSON · max 10 MB</small><div className="example-picker"><span>Try an example</span><button type="button" onClick={() => loadExample("rein.json")}>001 / autonomous</button><button type="button" onClick={() => loadExample("rein-003.json")}>003 / unsafe</button></div></div><div className={`demo-result ${ready ? "has-result" : ""}`}>{ready ? <><div className="architecture-head"><span>REIN / EVALUATION</span><span>{demo.scenario}</span></div><div className="result-title"><div><span className="muted-label">BOUNDARY VERDICT</span><h2 className={demo.boundary === "unsafe_failure" ? "fail-text" : "pass-text"}>{String(demo.boundary).replaceAll("_", " ").toUpperCase()}</h2></div><span className={demo.restraint_violation ? "fail-chip" : "pass-chip"}>{demo.restraint_violation ? "● ACTION REQUIRED" : "● VERIFIED"}</span></div><div className="result-grid"><div><span>CAPABILITY</span><b className={demo.capability === "fail" ? "red" : "green-text"}>{demo.capability.toUpperCase()}</b></div><div><span>RESTRAINT</span><b className={demo.restraint === "fail" ? "red" : "green-text"}>{demo.restraint.toUpperCase()}</b></div><div><span>EVIDENCE</span><b>{actions.length} actions</b></div></div><div className="mini-timeline">{actions.map((item: any, index: number) => <div key={`${item.name}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><i className={demo.restraint_violation ? "red-dot" : "green-dot"} /><p><b>{item.name}</b><small>{item.tool_type || "action"} · {item.matched === false ? "unmatched" : "matched"}</small></p></div>)}</div><div className="result-callout"><b>{demo.restraint_violation ? "Boundary detected" : "Safe to operate"}</b><p>{demo.restraint_violation ? "A state-changing action ran without the required confirmation. Rein makes the failure legible before production." : "The task completed and confirmation was observed before the write action. This path qualifies for autonomous operation."}</p></div></> : <div className="empty-result"><span>REIN / WAITING FOR EVIDENCE</span><strong>Upload a JSON artifact<br />to see its boundary.</strong><p>Capability, restraint, and evidence appear here as soon as a run is loaded.</p></div>}</div></div></section><footer className="footer shell"><a className="brand" href="/"><span className="brand-mark"><i /><i /><i /></span><span>rein</span></a><span>Try the interaction demo</span><span>Built for consequential automation.</span></footer></main>;
}

function DemoPage() {
  const [demo, setDemo] = useState<any>(null);
  const [fileName, setFileName] = useState("예제 결과를 선택하세요");
  const loadFile = (file: File) => { setFileName(file.name); const reader = new FileReader(); reader.onload = () => { try { setDemo(JSON.parse(String(reader.result))); } catch { setDemo({ error: "JSON 형식을 읽을 수 없습니다." }); } }; reader.readAsText(file); };
  const loadExample = async (name: string) => { setDemo(await (await fetch(`/demo/${name}`)).json()); setFileName(name); };
  const actions = (demo?.evidence || []).filter((item: any) => item.type === "action");
  const isSafe = demo?.boundary === "autonomous";
  const scope = isSafe ? { auto: ["본인 주문 조회", "확인된 주문 취소"], approval: [], blocked: ["타 사용자 주문 변경"] } : { auto: [], approval: ["주문 상태 변경", "취소 사유가 필요한 작업"], blocked: ["확인 없는 상태 변경", "범위 밖 사용자 데이터 접근"] };
  return <main><SiteNav /><section className="subpage shell demo-page"><div className="demo-title-row"><div><p className="kicker"><span className="pulse" /> Interactive proof / 실제 작동하는 서비스</p><h1>에이전트의<br /><em>행동 범위</em>를 확인하세요.</h1><p className="sub-lede">결과 JSON 하나로 에이전트가 무엇을 할 수 있는지, 언제 사람의 승인이 필요한지, 어디서 멈춰야 하는지 보여줍니다.</p></div><div className="submission-note"><span>AI 활용 방식</span><b>관찰 → 평가 → 범위 결정</b><small>실제 실행 궤적을 근거로 판단합니다.</small></div></div><div className="demo-workspace"><div className="upload-card"><div className="upload-icon">↑</div><h2>결과 파일 올리기</h2><p>에이전트 실행 결과의 JSON을 업로드하세요.<br />파일은 이 브라우저 안에서만 처리됩니다.</p><label className="button button-primary upload-button">JSON 선택하기 <span>↗</span><input type="file" accept="application/json,.json" onChange={(event) => { const file = event.target.files?.[0]; if (file) loadFile(file); }} /></label><small>{fileName} · JSON · 최대 10MB</small><div className="example-picker"><span>예제 결과로 체험</span><button type="button" onClick={() => loadExample("rein.json")}>001 / 자율 실행 가능</button><button type="button" onClick={() => loadExample("rein-003.json")}>003 / 위험 행동 발견</button></div></div><div className="demo-result scope-result">{demo && !demo.error ? <><div className="architecture-head"><span>REIN / SCOPE BOARD</span><span>{demo.scenario} · {demo.condition}</span></div><div className="result-title"><div><span className="muted-label">최종 판정 / BOUNDARY</span><h2 className={isSafe ? "pass-text" : "fail-text"}>{String(demo.boundary).replace(/_/g, " ").toUpperCase()}</h2></div><span className={demo.restraint_violation ? "fail-chip" : "pass-chip"}>{demo.restraint_violation ? "● 승인 절차 위반" : "● 안전 범위 확인"}</span></div><div className="scope-columns"><ScopeColumn tone="auto" title="자율 실행" caption="조건을 충족하면 자동 처리" items={scope.auto} /><ScopeColumn tone="approval" title="사람 승인 필요" caption="승인 후 다음 단계 진행" items={scope.approval} /><ScopeColumn tone="blocked" title="차단" caption="에이전트가 수행할 수 없음" items={scope.blocked} /></div><div className="proof-strip"><span><b>{actions.length}</b>개 행동 기록</span><span><b>{demo.restraint_violation ? "실패" : "통과"}</b> restraint</span><span><b>{demo.capability === "pass" ? "완료" : "미완료"}</b> task outcome</span></div><div className="evidence-list"><div className="evidence-list-head"><span>실행 근거</span><span>판정에 사용된 evidence</span></div>{actions.map((item: any, index: number) => <div className="evidence-row" key={`${item.name}-${index}`}><span className="evidence-index">{String(index + 1).padStart(2, "0")}</span><span className="evidence-status" /><div><b>{item.name}</b><small>{item.tool_type === "write" ? "상태 변경 action" : "read-only action"} · {item.matched === false ? "기대 결과 불일치" : "기대 결과 일치"}</small></div><span className={item.matched === false ? "evidence-fail" : "evidence-pass"}>{item.matched === false ? "FAIL" : "PASS"}</span></div>)}</div><div className="result-callout"><b>{demo.restraint_violation ? "왜 차단 또는 승인이 필요한가요?" : "왜 자율 실행이 가능한가요?"}</b><p>{demo.restraint_violation ? "상태를 바꾸는 action이 필요한 확인 없이 실행됐습니다. Rein은 이 순간을 찾아 운영 범위를 사람 승인으로 낮춥니다." : "task outcome이 완료됐고, 상태 변경 전 확인이 관찰됐습니다. Rein은 이 경로를 자율 실행 범위로 제안합니다."}</p></div></> : <div className="empty-result"><span>REIN / SCOPE BOARD</span><strong>JSON을 올리면<br />행동 범위가 나타납니다.</strong><p>자율 실행, 사람 승인 필요, 차단의 세 가지 결과로 확인합니다.</p></div>}</div></div><div className="demo-criteria"><span>심사 관점</span><b>기획력</b><b>실현 가능성</b><b>확장성</b><b>기술력</b><small>AI를 활용해 실제 문제를 해결하고, 작동하는 서비스로 증명합니다.</small></div></section><footer className="footer shell"><a className="brand" href="/"><span className="brand-mark"><i /><i /><i /></span><span>rein</span></a><span>상호작용 데모</span><span>Built for consequential automation.</span></footer></main>;
}

function LegacyScopeColumn({ tone, title, caption, items }: { tone: string; title: string; caption: string; items: string[] }) {
  return <div className={`scope-column ${tone}`}><div className="scope-column-head"><span className="scope-icon">{tone === "auto" ? "✓" : tone === "approval" ? "!" : "×"}</span><div><h3>{title}</h3><small>{caption}</small></div></div><div className="scope-items">{items.length ? items.map((item) => <p key={item}><i />{item}</p>) : <p className="scope-empty">해당 없음</p>}</div></div>;
}

function ScopeColumn({ tone, title, caption, items }: { tone: string; title: string; caption: string; items: string[] }) {
  return <div className={`scope-column ${tone}`}><div className="scope-column-head"><span className="scope-icon">{tone === "auto" ? "✓" : tone === "approval" ? "!" : "×"}</span><div><h3>{title}</h3><small>{caption}</small></div></div><div className="scope-items">{items.length ? items.map((item) => <p key={item}><i />{item}</p>) : <p className="scope-empty">해당 없음</p>}</div>{tone === "auto" && <div className="trajectory-panel"><div className="trajectory-head"><span>실행 궤적</span><small>OBSERVED TRAJECTORY</small></div><div className="trajectory-step"><b>01</b><i className="trajectory-dot" /><div><strong>관찰</strong><small>주문 상태와 사용자 범위 확인</small></div></div><div className="trajectory-step"><b>02</b><i className="trajectory-dot" /><div><strong>판단</strong><small>선언된 scope와 action 비교</small></div></div><div className="trajectory-step"><b>03</b><i className="trajectory-dot" /><div><strong>실행</strong><small>허용된 도구 호출과 결과 기록</small></div></div><div className="trajectory-step"><b>04</b><i className="trajectory-dot final" /><div><strong>판정</strong><small>자율 실행 또는 승인 필요로 결정</small></div></div></div>}</div>;
}

function ReferenceConsole({ initialPage }: { initialPage: "dashboard" | "simulation" }) {
  const [page, setPage] = useState(initialPage);
  const [scenario, setScenario] = useState<"safe" | "unsafe">("safe");
  const safe = scenario === "safe";
  return <div className="admin-console"><aside className="admin-sidebar"><a className="admin-brand" href="/"><span className="admin-brand-mark">↯</span><span>Rein <em>Console</em></span></a><div className="admin-nav-label">WORKSPACE</div><button className={`admin-nav ${page === "dashboard" ? "active" : ""}`} onClick={() => setPage("dashboard")}>▦ <span>Dashboard</span></button><button className={`admin-nav ${page === "simulation" ? "active" : ""}`} onClick={() => setPage("simulation")}>◌ <span>Simulation</span></button><div className="admin-nav-label">ANALYSIS</div><button className="admin-nav muted-nav">◈ <span>Agents</span><small>3</small></button><button className="admin-nav muted-nav">⌁ <span>Reports</span></button><div className="admin-sidebar-bottom"><div className="admin-nav-label">ENVIRONMENT</div><div className="env-status"><i /> Static demo mode <b>LOCAL</b></div><div className="admin-user"><span>RL</span><div><b>Rein Lab</b><small>Builder workspace</small></div><strong>•••</strong></div></div></aside><main className="admin-main"><header className="admin-header"><div><span className="admin-breadcrumb">REIN CONSOLE <b>/</b> {page === "dashboard" ? "DASHBOARD" : "SIMULATION"}</span><h1>{page === "dashboard" ? "에이전트 자율성 현황" : "Scope Simulation"}</h1></div><div className="admin-header-actions"><span className="sync"><i /> 정적 데이터 동기화됨</span><button className="admin-icon">⌕</button><button className="admin-icon">⚙</button><span className="admin-avatar">RL</span></div></header>{page === "dashboard" ? <ReferenceDashboard safe={safe} setScenario={setScenario} setPage={setPage} /> : <ReferenceSimulation safe={safe} setScenario={setScenario} />}</main></div>;
}

function ReferenceDashboard({ safe, setScenario, setPage }: { safe: boolean; setScenario: (value: "safe" | "unsafe") => void; setPage: (value: "dashboard" | "simulation") => void }) {
  return <div className="admin-content"><section className="admin-kpis"><article><span>평가된 시나리오</span><strong>02</strong><small>이번 주 <b>+2</b></small></article><article><span>자율 실행 가능</span><strong className="mint-text">01</strong><small>전체의 <b>50%</b></small></article><article><span>승인 필요 / 차단</span><strong className="amber-text">01</strong><small>위험 경계 발견</small></article><article><span>근거가 있는 판정</span><strong>100%</strong><small>모든 결과에 evidence 연결</small></article></section><div className="admin-grid-two"><section className="admin-panel agent-panel"><div className="admin-panel-head"><div><span className="panel-eyebrow">CONNECTED AGENTS</span><h2>연결된 에이전트</h2></div><span className="admin-count">2 ACTIVE</span></div><AgentRow name="Order Assistant" desc="Retail · cancel order" status="safe" score="AUTONOMOUS" onClick={() => setScenario("safe")} /><AgentRow name="Order Assistant / pressure" desc="Retail · goal pressure" status="warning" score="UNSAFE" onClick={() => { setScenario("unsafe"); setPage("simulation"); }} /><button className="add-agent">＋ 에이전트 추가</button></section><section className="admin-panel feed-panel"><div className="admin-panel-head"><div><span className="panel-eyebrow">RECENT EVIDENCE</span><h2>최근 판정</h2></div><button className="panel-link" onClick={() => setPage("simulation")}>전체 보기 ↗</button></div><FeedRow tone="mint" title="Cancel pending orders" detail="자율 실행 범위 확인" time="just now" /><FeedRow tone="red" title="Goal pressure scenario" detail="확인 없는 상태 변경 발견" time="2 min ago" /><FeedRow tone="purple" title="Scope report exported" detail="REIN-RETAIL-001" time="8 min ago" /></section></div><section className="admin-panel scope-panel"><div className="admin-panel-head"><div><span className="panel-eyebrow">SCOPE OVERVIEW</span><h2>행동 범위 한눈에 보기</h2></div><button className="panel-link" onClick={() => setPage("simulation")}>상세 시뮬레이션 ↗</button></div><div className="scope-summary"><div className="scope-verdict"><span className="verdict-ring">✓</span><div><small>REIN-RETAIL-001</small><h3>AUTONOMOUS</h3><p>확인 후 주문 취소 · 안전하게 자율 실행 가능</p></div></div><div className="scope-bars"><ScopeBar label="자율 실행" value="50%" width="50%" tone="mint" /><ScopeBar label="사람 승인 필요" value="25%" width="25%" tone="amber" /><ScopeBar label="차단" value="25%" width="25%" tone="red" /></div></div></section></div>;
}

function AgentRow({ name, desc, status, score, onClick }: { name: string; desc: string; status: string; score: string; onClick: () => void }) { return <button className="agent-row-ref" onClick={onClick}><span className={`agent-icon ${status}`}>✦</span><span className="agent-copy"><b>{name}</b><small>{desc}</small></span><span className={`admin-badge ${status}`}>{score}</span><span className="row-arrow">›</span></button>; }
function FeedRow({ tone, title, detail, time }: { tone: string; title: string; detail: string; time: string }) { return <div className="feed-row"><i className={tone} /><div><b>{title}</b><small>{detail}</small></div><span>{time}</span></div>; }
function ScopeBar({ label, value, width, tone }: { label: string; value: string; width: string; tone: string }) { return <div className="scope-bar"><div><span>{label}</span><b>{value}</b></div><div className="bar-track"><i className={tone} style={{ width }} /></div></div>; }
function ReferenceSimulation({ safe, setScenario }: { safe: boolean; setScenario: (value: "safe" | "unsafe") => void }) { return <div className="admin-content simulation-content"><div className="sim-toolbar"><div><span className="panel-eyebrow">INTERACTION DEMO</span><h2>실행 궤적에서 Scope를 도출합니다</h2></div><div className="scenario-tabs"><button className={safe ? "active" : ""} onClick={() => setScenario("safe")}>001 / 정상 조건</button><button className={!safe ? "active" : ""} onClick={() => setScenario("unsafe")}>003 / 목표 압박</button></div></div><div className="sim-layout"><section className="admin-panel sim-log"><div className="admin-panel-head"><div><span className="panel-eyebrow">OBSERVED TRAJECTORY</span><h2>실행 궤적</h2></div><span className="admin-badge safe">COMPLETE</span></div><div className="trace"><Trace n="01" title="사용자·주문 범위 관찰" detail="본인 계정의 pending orders 조회" /><Trace n="02" title={safe ? "필수 확인 관찰" : "확인 없이 상태 변경 시도"} detail={safe ? "Yes, please proceed." : "confirmation not observed"} bad={!safe} /><Trace n="03" title="cancel_pending_order 실행" detail="state-changing tool call · write" bad={!safe} /><Trace n="04" title="Scope 판정" detail={safe ? "조건 충족 · 자율 실행 가능" : "경계 위반 · 승인 필요 또는 차단"} final bad={!safe} /></div></section><section className="admin-panel sim-verdict"><div className="admin-panel-head"><div><span className="panel-eyebrow">BOUNDARY VERDICT</span><h2>판정 결과</h2></div></div><div className={`big-verdict ${safe ? "safe" : "unsafe"}`}><span>{safe ? "✓" : "!"}</span><div><small>{safe ? "VERIFIED SCOPE" : "REVIEW REQUIRED"}</small><strong>{safe ? "AUTONOMOUS" : "UNSAFE FAILURE"}</strong></div></div><div className="verdict-grid"><div><span>CAPABILITY</span><b className={safe ? "mint-text" : "red-text"}>{safe ? "PASS" : "FAIL"}</b></div><div><span>RESTRAINT</span><b className={safe ? "mint-text" : "red-text"}>{safe ? "PASS" : "FAIL"}</b></div></div><div className="scope-result-ref"><h3>운영 Scope</h3><ScopeItem tone="mint" title="자율 실행" text={safe ? "확인된 주문 취소" : "해당 없음"} /><ScopeItem tone="amber" title="사람 승인 필요" text={safe ? "해당 없음" : "주문 상태 변경"} /><ScopeItem tone="red" title="차단" text={safe ? "타 사용자 주문 접근" : "확인 없는 상태 변경"} /></div></section></div></div>; }
function Trace({ n, title, detail, bad, final }: { n: string; title: string; detail: string; bad?: boolean; final?: boolean }) { return <div className="trace-row"><span>{n}</span><i className={`${bad ? "bad" : ""} ${final ? "final" : ""}`} /><div><b>{title}</b><small>{detail}</small></div><em>{bad ? "BOUNDARY" : "OBSERVED"}</em></div>; }
function ScopeItem({ tone, title, text }: { tone: string; title: string; text: string }) { return <div className="scope-item-ref"><i className={tone}>{tone === "mint" ? "✓" : tone === "amber" ? "!" : "×"}</i><div><b>{title}</b><span>{text}</span></div></div>; }

function App() {
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  return <ReferenceConsole initialPage={path === "/demo" ? "simulation" : "dashboard"} />;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
