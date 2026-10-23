import Link from "next/link";

export function Loading({ text = "Loading..." }: { text?: string }) {
  return <p className="py-12 text-center font-bold text-ink/70">{text}</p>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-2xl border-2 border-ink bg-blush p-4 text-sm font-bold shadow-hard-sm">
      <p>{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 underline decoration-2 underline-offset-2">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="card py-16 text-center">
      <p className="font-serif text-lg font-bold">No requests yet</p>
      <Link href="/requests/new" className="btn-primary mt-4">
        Create request
      </Link>
    </div>
  );
}
