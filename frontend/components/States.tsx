import Link from "next/link";

export function Loading({ text = "Loading..." }: { text?: string }) {
  return <p className="py-12 text-center text-slate-500">{text}</p>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <p>{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 font-medium underline">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center">
      <p className="text-slate-600">No requests yet</p>
      <Link href="/requests/new" className="btn-primary mt-4">
        Create request
      </Link>
    </div>
  );
}
