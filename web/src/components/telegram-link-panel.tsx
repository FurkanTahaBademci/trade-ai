"use client";

import { useActionState } from "react";
import { checkTelegramAction, createTelegramLinkAction, type TelegramLinkState } from "@/app/hesap/bildirimler/actions";
import { AutoRefresh } from "./auto-refresh";

const primaryButton = "inline-flex h-10 items-center rounded bg-[var(--primary)] px-4 text-xs font-semibold text-[var(--primary-contrast)] transition hover:bg-[var(--primary-strong)] disabled:cursor-wait disabled:opacity-60";

function Message({ state }: { state: TelegramLinkState }) {
  if (!state.message) return null;
  return <p role={state.ok ? "status" : "alert"} className="text-xs leading-5" style={{ color: state.ok ? "var(--positive)" : "var(--negative)" }}>{state.message}</p>;
}

/**
 * İki adım: tek kullanımlık t.me bağlantısı üretilir, kullanıcı bot'ta "Başlat"a
 * basar. Worker dakikada bir mesajları işler; sayfa 10 sn'de bir yenilenir,
 * "Kontrol et" ise beklemeden işletir.
 */
export function TelegramLinkPanel() {
  const [link, createLink, creating] = useActionState(createTelegramLinkAction, {});
  const [check, runCheck, checking] = useActionState(checkTelegramAction, {});

  if (!link.url) {
    return <form action={createLink} className="space-y-3">
      <p className="text-xs leading-5 text-[var(--text-secondary)]">Bağladığında bot yalnız sana özel bildirim gönderir. İstediğin an bot'a /stop yazarak ya da buradan bağlantıyı kaldırabilirsin.</p>
      <button disabled={creating} className={primaryButton}>{creating ? "Hazırlanıyor…" : "Telegram'ı bağla"}</button>
      <Message state={link}/>
    </form>;
  }
  return <div className="space-y-4">
    <AutoRefresh intervalMs={10_000}/>
    <ol className="list-decimal space-y-2 pl-4 text-xs leading-5 text-[var(--text-secondary)]">
      <li>Aşağıdaki düğmeyle Telegram'da bot'u aç ve <span className="font-medium text-[var(--text)]">Başlat</span>'a bas. Bağlantı 30 dakika geçerli ve tek kullanımlık.</li>
      <li>Bot “hesabın bağlandı” yazınca bu sayfa kendiliğinden güncellenir (en geç bir dakika). Beklemek istemezsen “Kontrol et”e bas.</li>
    </ol>
    <div className="flex flex-wrap items-center gap-2">
      <a href={link.url} target="_blank" rel="noopener noreferrer" className={primaryButton}>Telegram'da aç</a>
      <form action={runCheck}><button disabled={checking} className="pill h-10 hover:text-[var(--text)]">{checking ? "Kontrol ediliyor…" : "Kontrol et"}</button></form>
    </div>
    <Message state={check}/>
  </div>;
}
