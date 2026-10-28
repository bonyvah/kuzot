import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { emailError } from "../auth/validation";
import { AccountChip } from "../components/AccountChip";
import { AuthCard } from "../components/AuthCard";
import { Button } from "../components/Button";
import { TextField } from "../components/TextField";

type Step = "email" | "password";

export function SignInPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const goTo = (next: Step) => {
    setError(null);
    setStep(next);
  };

  const submitEmail = () => {
    const problem = emailError(email);
    if (problem) return setError(problem);
    setEmail(email.trim());
    goTo("password");
  };

  const submitPassword = async () => {
    if (!password) return setError("Enter a password");
    setBusy(true);
    setError(null);
    try {
      // On success the auth state flips and <RedirectIfAuthed> navigates away.
      await signIn(email, password);
    } catch (err) {
      setError(signInError(err));
      setBusy(false);
    }
  };

  // Keep the post-login destination when switching to sign-up.
  const createAccount = () => navigate("/signup", { state: location.state });

  if (step === "email") {
    return (
      <AuthCard
        key="email"
        title="Sign in"
        subtitle="to continue to Kuzot"
        onSubmit={submitEmail}
        actions={
          <>
            <Button variant="text" onClick={createAccount}>
              Create account
            </Button>
            <Button type="submit">Next</Button>
          </>
        }
      >
        <TextField
          label="Email"
          type="email"
          autoComplete="username"
          autoFocus
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={error}
        />
        <Link to="/recovery/email" className="auth-card__link">
          Forgot email?
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      key="password"
      title="Welcome"
      subtitle={<AccountChip email={email} onClick={() => goTo("email")} />}
      busy={busy}
      onSubmit={submitPassword}
      actions={<Button type="submit">Next</Button>}
    >
      {/* Lets password managers pair the saved password with this email. */}
      <input type="email" autoComplete="username" value={email} readOnly hidden />
      <TextField
        label="Enter your password"
        type={showPassword ? "text" : "password"}
        autoComplete="current-password"
        autoFocus
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={error}
      />
      <label className="auth-card__check">
        <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} />
        Show password
      </label>
      <Link to="/recovery/password" className="auth-card__link">
        Forgot password?
      </Link>
    </AuthCard>
  );
}

function signInError(err: unknown): string {
  if (err instanceof ApiError) {
    // 422 means the password failed server-side validation (e.g. too short), so it is wrong too.
    if (err.status === 401 || err.status === 422) return "Wrong email or password. Try again.";
    return err.message;
  }
  return "Couldn't sign you in. Check your connection and try again.";
}
