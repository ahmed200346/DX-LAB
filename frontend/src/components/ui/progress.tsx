import * as React from "react"
import { cn } from "@/lib/utils"

function Progress({
  className,
  value,
  indicatorClassName,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  value?: number;
  indicatorClassName?: string;
}) {
  return (
    <div
      data-slot="progress"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-primary/20",
        className
      )}
      {...props}
    >
      <div
        data-slot="progress-indicator"
        className={cn(
          "h-full bg-primary transition-all duration-500 ease-out",
          indicatorClassName
        )}
        style={{ width: `${value || 0}%` }}
      />
    </div>
  )
}

export { Progress }
