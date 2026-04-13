import { useToast } from "@/hooks/use-toast";
import { Toast, ToastClose, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from "@/components/ui/toast";
import { CircleAlert, CheckCircle2 } from "lucide-react";

export function Toaster() {
  const { toasts } = useToast();

  return (
    <ToastProvider>
      {toasts.map(function ({ id, title, description, action, ...props }) {
        const Icon = props.variant === "destructive" ? CircleAlert : CheckCircle2;
        return (
          <Toast key={id} {...props}>
            <div className="flex items-start gap-3">
              <span className="mt-0.5 shrink-0">
                <Icon
                  className={props.variant === "destructive" ? "h-4.5 w-4.5 text-rose-600" : "h-4.5 w-4.5 text-emerald-600"}
                  strokeWidth={2.1}
                />
              </span>
              <div className="grid gap-1">
                {title && <ToastTitle>{title}</ToastTitle>}
                {description && <ToastDescription>{description}</ToastDescription>}
              </div>
            </div>
            {action}
            <ToastClose />
          </Toast>
        );
      })}
      <ToastViewport />
    </ToastProvider>
  );
}
