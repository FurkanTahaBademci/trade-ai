import Link from "next/link";
import { Icon } from "@/components/icon";

export default function NotFound() { return <div className="grid min-h-[65vh] place-items-center text-center"><div><p className="text-7xl font-semibold tracking-[-0.06em] text-[var(--primary)]">404</p><h1 className="mt-4 text-xl font-semibold">Sayfa bulunamadı</h1><p className="mt-2 text-sm text-[var(--text-muted)]">Aradığınız içerik taşınmış veya artık mevcut olmayabilir.</p><Link href="/" className="mt-6 inline-flex items-center gap-2 rounded bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-[var(--primary-contrast)]">Genel bakışa dön <Icon name="arrow" size={15}/></Link></div></div>; }
