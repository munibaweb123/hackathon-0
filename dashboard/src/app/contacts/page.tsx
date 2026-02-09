"use client";

import { useState, useEffect } from "react";

interface PlatformIdentity {
  platform: string;
  platform_id: string;
  display_name: string | null;
  profile_url: string | null;
  linked_by: string;
}

interface Contact {
  id: string;
  primary_email: string;
  display_name: string | null;
  company: string | null;
  identities: PlatformIdentity[];
  created_at: string;
}

const platformColors: Record<string, string> = {
  xero: "bg-blue-100 text-blue-800",
  linkedin: "bg-sky-100 text-sky-800",
  twitter: "bg-indigo-100 text-indigo-800",
  facebook: "bg-blue-100 text-blue-800",
  instagram: "bg-pink-100 text-pink-800",
  email: "bg-gray-100 text-gray-800",
  whatsapp: "bg-green-100 text-green-800",
};

export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchContacts();
  }, []);

  async function fetchContacts() {
    try {
      const res = await fetch("/api/contacts");
      if (res.ok) {
        const data = await res.json();
        setContacts(Array.isArray(data) ? data : data.contacts || []);
      }
    } catch {
      // API unavailable
    } finally {
      setLoading(false);
    }
  }

  const filtered = search
    ? contacts.filter(
        (c) =>
          c.primary_email.toLowerCase().includes(search.toLowerCase()) ||
          (c.display_name || "").toLowerCase().includes(search.toLowerCase()) ||
          (c.company || "").toLowerCase().includes(search.toLowerCase())
      )
    : contacts;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Unified Contacts</h2>
        <p className="text-muted-foreground">
          Cross-platform contact directory ({contacts.length} contacts)
        </p>
      </div>

      <input
        type="text"
        placeholder="Search by name, email, or company..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-md rounded-md border px-3 py-2 text-sm"
      />

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading contacts...</p>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border bg-card p-8 text-center">
          <p className="text-muted-foreground">
            {contacts.length === 0
              ? "No contacts yet. Contacts are automatically created when the AI processes events across platforms."
              : "No contacts match your search."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((contact) => (
            <div key={contact.id} className="rounded-lg border bg-card p-4">
              <div className="mb-2">
                <h3 className="font-semibold">
                  {contact.display_name || contact.primary_email}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {contact.primary_email}
                </p>
                {contact.company && (
                  <p className="text-sm text-muted-foreground">
                    {contact.company}
                  </p>
                )}
              </div>

              <div className="flex flex-wrap gap-1 mt-3">
                {contact.identities.map((identity, i) => (
                  <span
                    key={i}
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      platformColors[identity.platform] || "bg-gray-100"
                    }`}
                    title={`Linked via ${identity.linked_by}${identity.display_name ? ` as ${identity.display_name}` : ""}`}
                  >
                    {identity.platform}
                  </span>
                ))}
              </div>

              <p className="mt-3 text-xs text-muted-foreground">
                Added {new Date(contact.created_at).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
