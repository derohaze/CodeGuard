import { useTheme } from "next-themes";
import { Toaster as Sonner, toast } from "sonner";
import { CheckCircle2, CircleAlert, Info, LoaderCircle, TriangleAlert } from "lucide-react";

type ToasterProps = React.ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      position="top-center"
      className="toaster group"
      icons={{
        success: <CheckCircle2 className="size-4.5 text-emerald-600" strokeWidth={2.1} />,
        error: <CircleAlert className="size-4.5 text-rose-600" strokeWidth={2.1} />,
        warning: <TriangleAlert className="size-4.5 text-amber-600" strokeWidth={2.1} />,
        info: <Info className="size-4.5 text-sky-600" strokeWidth={2.1} />,
        loading: <LoaderCircle className="size-4.5 animate-spin text-[#8b7355]" strokeWidth={2.1} />,
      }}
      toastOptions={{
        classNames: {
          toast:
            "group toast relative min-h-11 rounded-[20px] border-0 px-4 py-2.5 pr-4 group-[.toaster]:bg-background group-[.toaster]:text-foreground shadow-[0_10px_24px_rgba(52,42,28,0.06)]",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
          title: "text-[14px] font-medium tracking-[-0.01em] text-txt-primary",
          description: "text-[13px] leading-6 text-txt-secondary",
          icon: "mr-1 shrink-0",
        },
      }}
      {...props}
    />
  );
};

export { Toaster, toast };
