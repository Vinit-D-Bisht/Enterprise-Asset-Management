"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Boxes, Check, CircleCheck, CircleHelp, LockKeyhole, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";
import { validateSetupDetails } from "@/lib/setup";

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [setupRequired, setSetupRequired] = useState<boolean | null>(null);
  const [setupStatusError, setSetupStatusError] = useState("");
  const [setupStep, setSetupStep] = useState(1);
  const [setupName, setSetupName] = useState("");
  const [setupEmail, setSetupEmail] = useState("");
  const [setupPassword, setSetupPassword] = useState("");
  const [setupConfirmation, setSetupConfirmation] = useState("");
  const [sampleData, setSampleData] = useState<boolean | null>(null);
  const [setupError, setSetupError] = useState("");
  const [setupBusy, setSetupBusy] = useState(false);
  const [setupComplete, setSetupComplete] = useState(false);

  useEffect(() => { if (!loading && user) router.replace("/dashboard"); }, [loading, user, router]);

  useEffect(() => {
    let active = true;
    void api.setupStatus().then((result) => { if (active) setSetupRequired(result.setup_required); }).catch((reason: unknown) => {
      if (active) setSetupStatusError(reason instanceof ApiError ? reason.message : "EAMMS setup status could not be checked.");
    });
    return () => { active = false; };
  }, []);

  async function submitSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSetupError("");
    if (setupStep === 1) { const validation = validateSetupDetails({ full_name: setupName, email: setupEmail, password: setupPassword, confirm_password: setupConfirmation }); if (validation) { setSetupError(validation); return; } setSetupStep(2); return; }
    if (sampleData === null) { setSetupError("Choose whether to include sample data."); return; }
    setSetupBusy(true);
    try {
      const result = await api.initialize({ full_name: setupName.trim(), email: setupEmail.trim(), password: setupPassword, confirm_password: setupConfirmation, sample_data: sampleData });
      if (!result.setup_complete) throw new Error("Setup did not complete. Please try again.");
      setSetupComplete(true);
    } catch (reason) { setSetupError(reason instanceof ApiError ? reason.message : reason instanceof Error ? reason.message : "Setup could not be completed. Please try again."); }
    finally { setSetupBusy(false); }
  }

  const busyOrChecking = loading || setupRequired === null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await login(email, password); router.replace("/dashboard"); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Unable to sign in. Check your connection and try again."); }
    finally { setBusy(false); }
  }

  return <main className="login-page">
    <section className="login-visual" aria-label="EAMMS platform overview">
      <div className="login-brand"><span className="brand-mark"><Boxes size={21} /></span><span><strong>EAMMS</strong><small>Asset operations platform</small></span></div>
      <div className="login-hero-copy">
        <span className="login-kicker"><CircleCheck size={14} /> Enterprise operations workspace</span>
        <h1>Keep every asset moving forward.</h1>
        <p>Bring asset records, maintenance coordination, and operational visibility together in one secure workspace.</p>
        <div className="login-value-list">
          <div className="login-value-item"><span className="login-feature-icon"><Boxes size={16} /></span><span>One clear view of asset lifecycle and custody</span><Check size={15} /></div>
          <div className="login-value-item"><span className="login-feature-icon"><Wrench size={16} /></span><span>Maintenance requests routed to the right people</span><Check size={15} /></div>
          <div className="login-value-item"><span className="login-feature-icon"><ShieldCheck size={16} /></span><span>Role-based access enforced at every step</span><Check size={15} /></div>
        </div>
      </div>
      <footer className="login-visual-footer"><span>Secure access for your organization</span><span>© {new Date().getFullYear()} EAMMS</span></footer>
    </section>
    <section className="login-form-panel">
      <div className="login-card">
        <div className="login-mobile-brand"><span className="brand-mark"><Boxes size={18} /></span><span><strong>EAMMS</strong><small>Asset operations platform</small></span></div>
        {setupRequired ? setupComplete ? <>
          <div className="login-form-icon login-success-icon"><Check size={20} /></div><p className="page-eyebrow">Workspace initialized</p><h2>Your EAMMS workspace is ready</h2><p>The initial Super Admin account has been created{sampleData ? " with sample data" : ""}. You can now sign in.</p><button className="button button-primary button-wide login-submit" type="button" onClick={() => router.replace("/login")}>Continue to sign in <ArrowRight size={16} /></button>
        </> : <>
        <div className="login-form-icon"><LockKeyhole size={19} /></div>
        <p className="page-eyebrow">First-run setup · Step {setupStep} of 3</p>
        <h2>{setupStep === 1 ? "Create your Super Admin" : "Configure your workspace"}</h2>
        <p>{setupStep === 1 ? "Set up the administrator account that will manage EAMMS." : "Choose how you would like to begin using EAMMS."}</p>
        {setupStep === 1 ? <form className="form-stack" onSubmit={(event) => void submitSetup(event)}>
          <label className="field"><span>Full name</span><input autoComplete="name" required minLength={2} maxLength={160} value={setupName} onChange={(event) => setSetupName(event.target.value)} /></label>
          <label className="field"><span>Email address</span><input type="email" autoComplete="email" required value={setupEmail} onChange={(event) => setSetupEmail(event.target.value)} placeholder="you@company.com" /></label>
          <label className="field"><span>Password <small className="field-hint">12–200 characters</small></span><input type="password" autoComplete="new-password" required minLength={12} maxLength={200} value={setupPassword} onChange={(event) => setSetupPassword(event.target.value)} /></label>
          <label className="field"><span>Confirm password</span><input type="password" autoComplete="new-password" required minLength={12} maxLength={200} value={setupConfirmation} onChange={(event) => setSetupConfirmation(event.target.value)} /></label>
          {setupError && <p className="alert alert-error" role="alert">{setupError}</p>}
          <button className="button button-primary button-wide login-submit" type="submit">Continue <ArrowRight size={16} /></button>
        </form> : <form className="form-stack" onSubmit={(event) => void submitSetup(event)}>
          <p className="setup-question">Would you like to populate EAMMS with realistic sample data?</p>
          <button className={`setup-choice ${sampleData === true ? "selected" : ""}`} type="button" aria-pressed={sampleData === true} onClick={() => setSampleData(true)}><span className="setup-choice-icon"><Sparkles size={18} /></span><span><strong>Yes, create sample data</strong><small>Explore assets, teams, vendors, maintenance, and reports with connected example records.</small></span><span className="setup-choice-radio" /></button>
          <button className={`setup-choice ${sampleData === false ? "selected" : ""}`} type="button" aria-pressed={sampleData === false} onClick={() => setSampleData(false)}><span className="setup-choice-icon setup-choice-empty"><CircleHelp size={18} /></span><span><strong>No, start empty</strong><small>Create only your administrator account and configure the workspace yourself.</small></span><span className="setup-choice-radio" /></button>
          <p className="setup-note">Sample data is optional. You can use it to explore EAMMS workflows and reports.</p>
          {setupError && <p className="alert alert-error" role="alert">{setupError}</p>}
          <div className="setup-actions"><button className="button button-secondary" type="button" onClick={() => { setSetupError(""); setSetupStep(1); }}><ArrowLeft size={15} /> Back</button><button className="button button-primary" type="submit" disabled={setupBusy || sampleData === null}>{setupBusy ? "Setting up workspace..." : <>Review & create <ArrowRight size={16} /></>}</button></div>
        </form>}
        </> : <>
        <div className="login-form-icon"><LockKeyhole size={19} /></div>
        <p className="page-eyebrow">Welcome back</p>
        <h2>Sign in to your workspace</h2>
        <p>Use your organization account to continue to EAMMS.</p>
        <form className="form-stack" onSubmit={(event) => void submit(event)}>
          <label className="field"><span>Email address</span><input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label>
          <label className="field"><span>Password</span><input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" /></label>
          {error && <p className="alert alert-error" role="alert">{error}</p>}
          <button className="button button-primary button-wide login-submit" type="submit" disabled={busy || busyOrChecking || Boolean(setupStatusError)}>{busy ? "Signing in..." : <>Sign in securely <ArrowRight size={16} /></>}</button>
        </form>
        <p className="login-footnote">Accounts are managed by your EAMMS administrator. If you need access, contact your organization administrator.</p>
        </>}
        {setupStatusError && <div className="setup-status-error" role="alert"><p>{setupStatusError}</p><button className="button button-secondary button-small" type="button" onClick={() => { setSetupStatusError(""); setSetupRequired(null); void api.setupStatus().then((result) => setSetupRequired(result.setup_required)).catch((reason: unknown) => setSetupStatusError(reason instanceof ApiError ? reason.message : "EAMMS setup status could not be checked.")); }}>Retry status check</button></div>}
        {setupRequired === null && !setupStatusError && <p className="setup-checking" role="status">Checking workspace setup...</p>}
      </div>
    </section>
  </main>;
}
