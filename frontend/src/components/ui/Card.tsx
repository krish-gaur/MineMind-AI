import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
  labelledBy?: string;
};

export function Card({ children, className = "", as: Tag = "section", labelledBy }: CardProps) {
  return (
    <Tag
      aria-labelledby={labelledBy}
      className={`rounded-lg border border-line bg-surface shadow-[0_1px_0_rgba(20,25,28,0.04)] ${className}`}
    >
      {children}
    </Tag>
  );
}

type CardHeaderProps = {
  title: string;
  id: string;
  description?: ReactNode;
  actions?: ReactNode;
};

export function CardHeader({ title, id, description, actions }: CardHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
      <div className="min-w-0">
        <h2 id={id} className="text-base font-semibold text-ink-900">
          {title}
        </h2>
        {description ? <p className="mt-1 text-sm text-ink-500">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
