import React from "react";
import { cn } from "@/utils/format";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "secondary" | "outline";

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: "bg-primary/15 text-primary border-primary/25",
  success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
  danger: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
  secondary: "bg-secondary text-secondary-foreground border-border",
  outline: "bg-transparent text-foreground border-border",
};

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        VARIANT_CLASSES[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
