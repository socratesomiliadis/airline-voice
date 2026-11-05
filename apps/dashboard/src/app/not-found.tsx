import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-20 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-3 text-sm text-slate-500">This workspace page does not exist.</p>
      <Link
        href="/"
        className="mt-6 inline-block text-sm font-medium text-emerald-700 underline underline-offset-4"
      >
        Return to overview
      </Link>
    </div>
  );
}
