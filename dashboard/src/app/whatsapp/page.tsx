import { WhatsAppLive } from "@/components/whatsapp-live";

export const dynamic = "force-dynamic";

export default function WhatsAppPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">WhatsApp</h2>
        <p className="text-muted-foreground">
          Silver Tier — WhatsApp Web monitoring via Playwright
        </p>
      </div>

      <WhatsAppLive />
    </div>
  );
}
