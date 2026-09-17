import { cn } from "@/client/lib/utils";

const TONES: Record<string, string> = {
  passing: "border-[#10b981]/40 bg-[#10b981]/10 text-[#10b981]",
  passed: "border-[#10b981]/40 bg-[#10b981]/10 text-[#10b981]",
  success: "border-[#10b981]/40 bg-[#10b981]/10 text-[#10b981]",
  failing: "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]",
  failed: "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]",
  failure: "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]",
  error: "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]",
  high: "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]",
  critical: "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]",
  medium: "border-[#f59e0b]/40 bg-[#f59e0b]/10 text-[#f59e0b]",
  stale: "border-[#f59e0b]/40 bg-[#f59e0b]/10 text-[#f59e0b]",
  safe: "border-[#10b981]/40 bg-[#10b981]/10 text-[#10b981]",
  blocked: "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]",
  needs_review: "border-[#f59e0b]/40 bg-[#f59e0b]/10 text-[#f59e0b]",
  met: "border-[#10b981]/40 bg-[#10b981]/10 text-[#10b981]",
  at_risk: "border-[#f59e0b]/40 bg-[#f59e0b]/10 text-[#f59e0b]",
  breached: "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]",
  not_linked: "border-border bg-muted text-muted-foreground",
};

export function StatusBadge({ value, label, className }: { value: string; label?: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium",
        TONES[value] ?? "border-border bg-muted text-muted-foreground",
        className,
      )}
    >
      {label ?? value}
    </span>
  );
}
