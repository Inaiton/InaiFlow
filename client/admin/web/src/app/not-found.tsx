import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto mt-24 max-w-md text-center">
      <h1 className="text-lg font-semibold text-ink">Page not found</h1>
      <Link href="/" className="mt-2 inline-block text-primary hover:underline">
        Back to dashboard
      </Link>
    </div>
  );
}
