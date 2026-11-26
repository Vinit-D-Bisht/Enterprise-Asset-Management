"use client";

import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

export function Modal({ open, title, description, onClose, children, size = "default" }: Readonly<{
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: React.ReactNode;
  size?: "default" | "wide";
}>) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className={`modal-card ${size === "wide" ? "modal-wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <header className="modal-heading"><div><h2 id={titleId}>{title}</h2>{description && <p>{description}</p>}</div><button ref={closeRef} className="icon-button" type="button" aria-label="Close dialog" onClick={onClose}><X size={19} /></button></header>
      {children}
    </section>
  </div>;
}
