import { label, type Priority, type Status } from "@/lib/types";

const PRIORITY_STYLES: Record<Priority, string> = {
  low: "bg-slate-100 text-slate-700",
  medium: "bg-blue-100 text-blue-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

const STATUS_STYLES: Record<Status, string> = {
  new: "bg-sky-100 text-sky-700",
  in_review: "bg-purple-100 text-purple-700",
  in_progress: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-slate-100 text-slate-600",
};

function Pill({ className, children }: { className: string; children: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
      {children}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Pill className={PRIORITY_STYLES[priority]}>{label(priority)}</Pill>;
}

export function StatusBadge({ status }: { status: Status }) {
  return <Pill className={STATUS_STYLES[status]}>{label(status)}</Pill>;
}
