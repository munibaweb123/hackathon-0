import { LinkedInLive } from "@/components/linkedin-live";

export const dynamic = "force-dynamic";

export default function LinkedInPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">LinkedIn</h2>
        <p className="text-muted-foreground">
          Connect and manage your LinkedIn presence
        </p>
      </div>

      <LinkedInLive />
    </div>
  );
}
