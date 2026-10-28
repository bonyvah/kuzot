const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Mirrors RegisterRequest / LoginRequest in backend/app/schemas/auth.py.
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 128;

export function emailError(email: string): string | null {
  const value = email.trim();
  if (!value) return "Enter an email";
  if (!EMAIL_RE.test(value)) return "Enter a valid email";
  return null;
}

export function newPasswordError(password: string): string | null {
  if (!password) return "Enter a password";
  if (password.length < PASSWORD_MIN) return `Use ${PASSWORD_MIN} characters or more for your password`;
  if (password.length > PASSWORD_MAX) return `Use ${PASSWORD_MAX} characters or fewer for your password`;
  return null;
}
