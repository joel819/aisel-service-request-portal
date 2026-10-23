import { label, type Priority, type Status } from "@/lib/types";

const PRIORITY_STYLES: Record<Priority, string> = {
  low: "bg-fog",
  medium: "bg-sky",
  high: "bg-amber",
  critical: "bg-flame",
};

const STATUS_STYLES: Record<Status, string> = {
  new: "bg-lilac",
  in_review: "bg-sky",
  in_progress: "bg-sun",
  completed: "bg-mint",
  cancelled: "bg-fog",
};

function Pill({ className, children }: { className: string; children: string }) {
  return <span className={`chip ${className}`}>{children}</span>;
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Pill className={PRIORITY_STYLES[priority]}>{label(priority)}</Pill>;
}

export function StatusBadge({ status }: { status: Status }) {
  return <Pill className={STATUS_STYLES[status]}>{label(status)}</Pill>;
}
