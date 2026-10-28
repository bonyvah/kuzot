import { useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { emailError, newPasswordError, PASSWORD_MIN } from "../auth/validation";
import { AccountChip } from "../components/AccountChip";
import { AuthCard } from "../components/AuthCard";
import { Button } from "../components/Button";
import { TextField } from "../components/TextField";

type Step = "details" | "password";

interface Errors {
  email?: string | null;
  password?: string | null;
  confirm?: string | null;
  form?: string | null;
}

export function SignUpPage() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [step, setStep] = useState<Step>("details");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);

  const goTo = (next: Step, nextErrors: Errors = {}) => {
    setErrors(nextErrors);
    setStep(next);
  };

  const submitDetails = () => {
    const problem = emailError(email);
    if (problem) return setErrors({ email: problem });
    setEmail(email.trim());
    goTo("password");
  };

  const submitPassword = async () => {
    const problem = newPasswordError(password);
    if (problem) return setErrors({ password: problem });
    if (confirm !== password) return setErrors({ confirm: "Those passwords didn't match. Try again." });

    setBusy(true);
    setErrors({});
    try {
      // Registers, then signs in; <RedirectIfAuthed> navigates away on success.
      await signUp(email, password, fullName.trim() || null);
    } catch (err) {
      setBusy(false);
      if (err instanceof ApiError && err.status === 400 && /already registered/i.test(err.message)) {
        return goTo("details", { email: "That email is already registered. Try signing in instead." });
      }
      setErrors({
        form: err instanceof ApiError ? err.message : "Couldn't create your account. Check your connection and try again.",
      });
    }
  };

  const signInInstead = () => navigate("/signin", { state: location.state });

  if (step === "details") {
    return (
      <AuthCard
        key="details"
        title="Create a Kuzot Account"
        subtitle="Enter your name and email"
        onSubmit={submitDetails}
        actions={
          <>
            <Button variant="text" onClick={signInInstead}>
              Sign in instead
            </Button>
            <Button type="submit">Next</Button>
          </>
        }
      >
        <TextField
          label="Full name (optional)"
          autoComplete="name"
          autoFocus
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
        />
      </AuthCard>
    );
  }

  return (
    <AuthCard
      key="password"
      title="Create a strong password"
      subtitle={
        <>
          <AccountChip email={email} onClick={() => goTo("details")} />
          <p className="auth-card__hint">Use {PASSWORD_MIN} or more characters</p>
        </>
      }
      busy={busy}
      onSubmit={submitPassword}
      actions={<Button type="submit">Next</Button>}
    >
      {errors.form && (
        <p className="auth-card__form-error" role="alert">
          {errors.form}
        </p>
      )}
      <input type="email" autoComplete="username" value={email} readOnly hidden />
      <TextField
        label="Password"
        type={showPassword ? "text" : "password"}
        autoComplete="new-password"
        autoFocus
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        error={errors.password}
      />
      <TextField
        label="Confirm"
        type={showPassword ? "text" : "password"}
        autoComplete="new-password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        error={errors.confirm}
      />
      <label className="auth-card__check">
        <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} />
        Show password
      </label>
    </AuthCard>
  );
}
