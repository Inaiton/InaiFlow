"use client";

import { Building2, KeyRound, LogOut, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/core/auth/AuthProvider";
import { Avatar } from "@/components/ui/icon-tile";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

export function UserMenu() {
  const { user, logout, isImpersonating } = useAuth();
  const router = useRouter();
  const name = user?.full_name ?? (isImpersonating ? "Support session" : "Account");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-primary/40" aria-label="Account menu">
        <Avatar name={name} src={user?.avatar_url} size={40} />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64">
        <DropdownMenuLabel className="normal-case tracking-normal">
          <span className="block text-[13px] font-semibold text-fg">{name}</span>
          {user ? <span className="block truncate text-xs font-normal text-fg-muted">{user.email}</span> : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {isImpersonating ? null : (
          <>
            <DropdownMenuItem onSelect={() => router.push("/me")}><User /> Personal space</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => router.push("/me/organizations")}><Building2 /> My organizations</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => router.push("/me/security")}><KeyRound /> Profile & security</DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem destructive onSelect={() => void logout()}><LogOut /> {isImpersonating ? "End session" : "Sign out"}</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
