import type { ButtonHTMLAttributes } from "react";
import "./Button.css";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "filled" | "text";
}

export function Button({ variant = "filled", type = "button", className, ...rest }: ButtonProps) {
  return <button type={type} className={`btn btn--${variant}${className ? ` ${className}` : ""}`} {...rest} />;
}
