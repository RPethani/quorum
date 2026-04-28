import { cn } from "@/lib/utils";
import { forwardRef } from "react";
import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

const fieldBase =
  "w-full rounded-sm border border-border-default bg-elevated px-3 text-sm text-fg-primary " +
  "placeholder:text-fg-tertiary transition-colors duration-100 " +
  "focus-visible:outline-none focus-visible:border-accent-primary " +
  "focus-visible:ring-2 focus-visible:ring-accent-primary-weak " +
  "disabled:cursor-not-allowed disabled:opacity-50";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type = "text", ...props }, ref) => (
    <input ref={ref} type={type} className={cn(fieldBase, "h-9", className)} {...props} />
  ),
);
Input.displayName = "Input";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(fieldBase, "min-h-[6rem] py-2", className)} {...props} />
));
Textarea.displayName = "Textarea";
