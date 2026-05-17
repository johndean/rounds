/* eslint-disable no-undef */
// Login route — /login
// VIN Transcript Software branded sign-in screen. Logout button → /login.

function LoginRoute() {
  const [email, setEmail] = useState("kate.schultz@vin.com");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);

  async function signIn(e) {
    if (e) e.preventDefault();
    if (!email || !pw) { toast.push("Email and password required", { tone: "attn" }); return; }
    setBusy(true);
    await new Promise((r) => setTimeout(r, 420));
    setBusy(false);
    auditLog.log("You", "auth", `Signed in as ${email}`);
    toast.push(`Welcome back, ${email.split("@")[0]}`, { tone: "ok" });
    navigate("/dashboard");
  }

  return (
    <main className="login" data-screen-label="Login">
      <div className="login__bg" aria-hidden />
      <form className="login__card" onSubmit={signIn}>
        <div className="login__brand">
          <img src="assets/VIN.svg" alt="VIN" />
          <div className="login__brand-text">
            <div className="login__brand-name">TRANSCRIPT<strong>.SOFTWARE</strong></div>
            <div className="login__brand-sub">VIN Transcript Operations Console</div>
          </div>
        </div>

        <h1 className="login__title">Sign in</h1>
        <span className="login__pill">v4.0.0 · OPERATOR CONSOLE</span>
        <p className="login__lead">
          Audit-traceable transcription workflow for VIN continuing-education sessions · SOP-gated review · append-only correction lineage.
        </p>

        <label className="login__label">
          Email
          <input
            type="email"
            className="login__input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@vin.com"
            autoFocus
            data-test-id="login-email"
          />
        </label>

        <label className="login__label">
          Password
          <input
            type="password"
            className="login__input"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            placeholder="••••••••••••"
            data-test-id="login-password"
          />
        </label>

        <div className="login__row">
          <label className="login__remember">
            <input type="checkbox" defaultChecked /> Keep me signed in for 8 hours
          </label>
          <a href="#/login" className="login__forgot" onClick={(e) => { e.preventDefault(); toast.push("Password reset — email sent", { tone: "ok" }); }}>Forgot password?</a>
        </div>

        <button type="submit" className="login__submit" disabled={busy} data-test-id="login-submit">
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <div className="login__foot">
          <span>Build <code>v4.0.0-ssot-r2</code></span>
          <span>·</span>
          <span><a href="#/" onClick={(e) => { e.preventDefault(); toast.push("Status page (mock)"); }}>System status: nominal</a></span>
          <span>·</span>
          <span><a href="#/" onClick={(e) => { e.preventDefault(); toast.push("Privacy policy (mock)"); }}>Privacy</a></span>
        </div>
      </form>
    </main>
  );
}

window.LoginRoute = LoginRoute;
