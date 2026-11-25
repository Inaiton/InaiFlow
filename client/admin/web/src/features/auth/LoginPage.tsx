"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/states";
import { useAuth } from "@/core/auth/AuthProvider";
import { errorMessage } from "@/lib/api/errors";
import type { Schemas } from "@/lib/api/client";
import { loginSchema, type LoginValues } from "./schemas";
import { useAdminLogin } from "./api";
import { MfaStep } from "./MfaStep";

function safeNext(n: string | null): string {
  return n && n.startsWith("/") && !n.startsWith("//") && !n.startsWith("/\\") && !n.startsWith("/login") ? n : "/";
}

export function LoginPage() {
  const { status, signIn } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const login = useAdminLogin();
  const [challenge, setChallenge] = useState<Schemas["AdminLoginOut"] | null>(null);
  const form = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });

  useEffect(() => {
    if (status === "authenticated") router.replace(next);
  }, [status, router, next]);

  const onSubmit = form.handleSubmit((v) => login.mutate(v, { onSuccess: setChallenge }));
  const userWeb = process.env.NEXT_PUBLIC_USER_WEB_URL;

  return (
    <div className="flex min-h-screen items-center justify-center bg-sidebar px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <Image src="/brand/logo-light.png" alt="InaiFlow" width={120} height={32} className="h-7 w-auto" priority />
        <div className="mt-2 inline-block rounded-sm bg-primary-tint px-1.5 py-0.5 text-[10px] font-bold tracking-[0.12em] text-primary-hover">PLATFORM CONSOLE</div>
        <h1 className="mt-4 text-lg font-semibold text-ink">Superadmin sign in</h1>
        <p className="mb-5 text-[13px] text-muted">Separate from tenant accounts · platform admins only</p>
        {challenge ? (
          <MfaStep challenge={challenge} onDone={(r) => signIn(r)} onRestart={() => setChallenge(null)} />
        ) : (
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <Field label="Admin email" error={form.formState.errors.email?.message}>
              <Input type="email" autoComplete="username" {...form.register("email")} autoFocus />
            </Field>
            <Field label="Password" error={form.formState.errors.password?.message}>
              <Input type="password" autoComplete="current-password" {...form.register("password")} />
            </Field>
            {login.isError ? (
              <p role="alert" className="text-[13px] text-danger-ink">
                {errorMessage(login.error)}
              </p>
            ) : null}
            <Button type="submit" variant="primary" className="w-full" disabled={login.isPending}>
              {login.isPending ? <Spinner /> : null} Continue
            </Button>
          </form>
        )}
        <p className="mt-5 text-center text-xs text-faint">
          Tenant user?{" "}
          {userWeb ? (
            <a href={`${userWeb}/login`} className="text-primary hover:underline">
              Go to InaiFlow sign in
            </a>
          ) : (
            "Use the InaiFlow app sign in."
          )}
        </p>
      </div>
    </div>
  );
}
