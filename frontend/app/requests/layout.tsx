import { Header } from "@/components/Header";

export default function RequestsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </>
  );
}
