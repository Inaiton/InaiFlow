import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-white hover:bg-primary-hover",
        secondary: "border border-line bg-white text-ink-2 hover:bg-subtle",
        ghost: "text-muted hover:bg-subtle hover:text-ink-2",
        danger: "bg-danger text-white hover:bg-danger-ink",
        "danger-outline": "border border-danger/40 bg-white text-danger-ink hover:bg-danger-tint",
        link: "text-primary underline-offset-4 hover:underline px-0",
      },
      size: { sm: "h-8 px-2.5 text-[13px]", md: "h-9 px-3.5", lg: "h-10 px-4", icon: "size-8" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export type ButtonProps = ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean };

export function Button({ className, variant, size, asChild, type = "button", ...props }: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button";
  return <Comp type={asChild ? undefined : type} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
