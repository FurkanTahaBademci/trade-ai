import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Gizlilik ve kullanım koşulları" };

// Metin değişirse backend'deki TERMS_VERSION da artırılır (app/auth/service.py).
const TERMS_VERSION = "2026-10";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="mt-6"><h2 className="text-sm font-semibold">{title}</h2><div className="mt-2 space-y-2 text-sm leading-6 text-[var(--text-secondary)]">{children}</div></section>;
}

export default function PrivacyPage() {
  const contact = process.env.CONTACT_EMAIL;
  return <article className="max-w-3xl">
    <PageHeader eyebrow={`Sürüm ${TERMS_VERSION}`} title="Gizlilik ve kullanım koşulları" description="Hesap açtığında hangi verilerinin neden işlendiği ve platformu hangi koşullarla kullandığın."/>

    <Section title="Platform ne yapar, ne yapmaz">
      <p>TradeAI; Borsa İstanbul hisseleri için haber, KAP bildirimi, temel analiz ve kurumsal görüş verilerini birleştirip araştırma amaçlı skorlar üretir. Paper portföyler ve backtestler tamamen sanaldır; gerçek emir iletilmez, para ya da sermaye piyasası aracı tutulmaz.</p>
      <p><strong>Platformdaki hiçbir skor, sinyal, portföy ya da analiz yatırım tavsiyesi değildir.</strong> Kişiye özel yatırım danışmanlığı sunulmaz. Yatırım kararlarının sorumluluğu sana aittir. Veriler üçüncü taraf kaynaklardan gelir; gecikmeli, eksik ya da hatalı olabilir.</p>
    </Section>

    <Section title="Hangi kişisel verileri işliyoruz">
      <ul className="list-disc space-y-1 pl-5">
        <li><strong>Hesap bilgileri:</strong> e-posta adresi, görünen ad, parolanın tek yönlü özeti (parolanın kendisi saklanmaz), kayıt ve onay tarihleri, hesap rolü.</li>
        <li><strong>Oturum bilgileri:</strong> açık oturumlar için IP adresi, tarayıcı bilgisi ve son görülme zamanı. Oturum 30 gün sonra ya da çıkış yaptığında silinir.</li>
        <li><strong>Kullanım tercihleri:</strong> hesabına kaydettiğin izleme listesi.</li>
      </ul>
      <p>Pazarlama amaçlı e-posta gönderilmez; e-posta adresin yalnız doğrulama, parola sıfırlama ve hesap güvenliği bildirimleri için kullanılır. Verilerin satılmaz ve reklam amacıyla üçüncü taraflarla paylaşılmaz.</p>
    </Section>

    <Section title="İşleme amacı ve hukuki sebep">
      <p>Veriler, 6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) md. 5/2-c kapsamında hesabın oluşturulması ve hizmetin sunulması (sözleşmenin ifası), md. 5/2-f kapsamında hesap güvenliğinin sağlanması ve kötüye kullanımın önlenmesi (meşru menfaat) amaçlarıyla işlenir.</p>
      <p>Veriler platformun barındırıldığı sunucuda tutulur. E-postalar bir e-posta gönderim hizmeti aracılığıyla iletilir.</p>
    </Section>

    <Section title="Saklama süresi ve hakların">
      <p>Hesap verilerin hesabın açık kaldığı sürece saklanır. <Link href="/hesap" className="text-[var(--primary)]">Hesabım</Link> sayfasından hesabını istediğin an silebilirsin; silme işlemi hesap, oturum ve izleme listesi kayıtlarını kalıcı olarak kaldırır. Doğrulanmamış ve kullanılmayan bağlantılar süreleri dolunca otomatik silinir.</p>
      <p>KVKK md. 11 kapsamında verilerinin işlenip işlenmediğini öğrenme, düzeltilmesini ya da silinmesini isteme ve itiraz etme haklarına sahipsin.{contact ? <> Talepler için: <a href={`mailto:${contact}`} className="text-[var(--primary)]">{contact}</a>.</> : " Taleplerini kayıtlı e-posta adresinden iletebilirsin."}</p>
    </Section>

    <Section title="Kullanım koşulları">
      <ul className="list-disc space-y-1 pl-5">
        <li>Hesap kişiseldir; giriş bilgilerini paylaşmamakla ve güvenliğini sağlamakla yükümlüsün.</li>
        <li>Platformu otomatik araçlarla aşırı yükleyemez, verileri toplu olarak kopyalayıp yeniden dağıtamazsın.</li>
        <li>Kötüye kullanım hâlinde hesap devre dışı bırakılabilir. Hizmet önceden haber verilmeksizin değiştirilebilir ya da durdurulabilir.</li>
        <li>Platform açık kaynaklıdır ve &quot;olduğu gibi&quot; sunulur; kesintisiz ya da hatasız çalışacağı garanti edilmez.</li>
      </ul>
    </Section>
  </article>;
}
