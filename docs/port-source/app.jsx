/* eslint-disable no-undef */
// App root — router + theme + tweaks panel integration.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "brand": "vin",
  "density": "comfortable",
  "slideRailDefault": "focus",
  "showFlags": true,
  "showStatusBar": true
}/*EDITMODE-END*/;

function applyBrand(brand) {
  const root = document.documentElement;
  if (brand === "vspn") {
    root.style.setProperty("--surface-nav",     "#005842");
    root.style.setProperty("--color-navy",      "#007D61");
    root.style.setProperty("--color-navy-deep", "#005842");
    root.style.setProperty("--color-navy-focus","#006B50");
    root.style.setProperty("--text-accent",     "#0097A9");
    root.style.setProperty("--fg-link",         "#0097A9");
    root.style.setProperty("--fg1",             "#005842");
    root.style.setProperty("--text-primary",    "#005842");
  } else {
    root.style.removeProperty("--surface-nav");
    root.style.removeProperty("--color-navy");
    root.style.removeProperty("--color-navy-deep");
    root.style.removeProperty("--color-navy-focus");
    root.style.removeProperty("--text-accent");
    root.style.removeProperty("--fg-link");
    root.style.removeProperty("--fg1");
    root.style.removeProperty("--text-primary");
  }
}

function App() {
  const path = useHashRoute();
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  useEffect(() => {
    document.documentElement.dataset.theme = t.theme;
    document.documentElement.dataset.density = t.density;
    applyBrand(t.brand);
  }, [t.theme, t.brand, t.density]);

  // Global ⌘K to open command palette and ⌘F for Find&Replace (in editor)
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        wired.openCmdK();
      } else if ((e.metaKey || e.ctrlKey) && e.key === "f" && path.startsWith("/e/")) {
        e.preventDefault();
        wired.openFind();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [path]);

  // Route resolution
  let route;
  let m;
  if (matchRoute(path, "/login")) {
    route = <LoginRoute />;
  } else if (path === "" || path === "/" || matchRoute(path, "/dashboard")) {
    route = <DashboardRoute />;
  } else if (matchRoute(path, "/sessions")) {
    route = <SessionsRoute />;
  } else if (matchRoute(path, "/upload")) {
    route = <UploadRoute />;
  } else if ((m = matchRoute(path, "/v/:id"))) {
    route = <ViewerRoute id={m.params.id} />;
  } else if ((m = matchRoute(path, "/s/:id"))) {
    route = <SessionDetailRoute id={m.params.id} />;
  } else if ((m = matchRoute(path, "/e/:id/sop"))) {
    route = <SopRoute id={m.params.id} />;
  } else if ((m = matchRoute(path, "/e/:id/audit"))) {
    route = <AuditRoute id={m.params.id} />;
  } else if ((m = matchRoute(path, "/e/:id"))) {
    route = <EditorRoute id={m.params.id} />;
  } else if ((m = matchRoute(path, "/p/:id"))) {
    route = <ProcessingRoute id={m.params.id} />;
  } else if (matchRoute(path, "/improvements")) {
    route = <ImprovementsRoute />;
  } else if (matchRoute(path, "/audit")) {
    route = <AuditRoute />;
  } else if (matchRoute(path, "/gcs")) {
    route = <GcsRoute />;
  } else if (matchRoute(path, "/settings")) {
    route = <SettingsRoute />;
  } else {
    route = (
      <div className="page">
        <div className="page-eyebrow"><span>404</span></div>
        <h1 className="page-title">Route not found</h1>
        <p className="page-desc">Path <code>{path}</code> doesn't match any registered route. <Link to="/sessions">Back to Sessions →</Link></p>
      </div>
    );
  }

  const isLogin = path.startsWith("/login");
  return (
    <div className="app">
      {!isLogin ? <AppHeader /> : null}
      {route}

      {/* Tweaks panel — self-manages open state via host postMessage. */}
      <TweaksPanel title="Tweaks">
        <TweakSection label="Appearance">
          <TweakRadio label="Theme" value={t.theme}
            options={[{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }]}
            onChange={(v) => setTweak("theme", v)} />
          <TweakRadio label="Brand" value={t.brand}
            options={[{ value: "vin", label: "VIN" }, { value: "vspn", label: "VSPN" }]}
            onChange={(v) => setTweak("brand", v)} />
          <TweakRadio label="Density" value={t.density}
            options={[{ value: "comfortable", label: "Comfort" }, { value: "compact", label: "Compact" }]}
            onChange={(v) => setTweak("density", v)} />
        </TweakSection>
        <TweakSection label="Editor">
          <TweakRadio label="Slide-rail mode" value={t.slideRailDefault}
            options={[{ value: "focus", label: "Focus" }, { value: "filter", label: "Filter" }]}
            onChange={(v) => { setTweak("slideRailDefault", v); localStorage.setItem("mic_slide_click_mode", v); }} />
          <TweakToggle label="AI flag overlays"  value={t.showFlags}      onChange={(v) => setTweak("showFlags", v)} />
          <TweakToggle label="Debug status bar"  value={t.showStatusBar}  onChange={(v) => setTweak("showStatusBar", v)} />
        </TweakSection>
        <TweakSection label="Quick navigate">
          <div style={{ display: "grid", gap: 4, padding: "4px 0" }}>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/dashboard")}>Dashboard</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/sessions")}>Sessions list</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/upload")}>Upload</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/s/se_001")}>Session detail</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/e/se_001")}>Editor (Copy edit draft)</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/e/se_001/sop")}>SOP workflow</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/e/se_001/audit")}>Word Track Changes</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/v/se_004")}>Viewer</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/p/se_007")}>Processing</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/improvements")}>Improvements</button>
            <button className="btn btn--secondary btn--sm" onClick={() => navigate("/gcs")}>GCS QA</button>
          </div>
        </TweakSection>
      </TweaksPanel>

      {!t.showFlags ? (
        <style dangerouslySetInnerHTML={{ __html: `
          .word.flag-drift, .word.flag-uncertain, .word.flag-low_confidence {
            background: transparent !important; color: inherit !important;
            border-bottom-color: transparent !important;
          }`
        }} />
      ) : null}
      {!t.showStatusBar ? <style dangerouslySetInnerHTML={{ __html: ".editor__statusbar{display:none;}" }} /> : null}

      <ToastHost />
      <ConfirmHost />
      <ModalHost />
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("app"));
root.render(<App />);
