"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { supabase } from "@/lib/api";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let mounted = true;
    if (!supabase) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    const client = supabase;
    const verifySession = async () => {
      // Do not mount the workspace from an old local-storage token.  That was
      // allowing its one-time basket request to run before Supabase completed
      // the OAuth/session refresh, leaving the dashboard looking empty.
      const {
        data: { session },
      } = await client.auth.getSession();
      if (!session) throw new Error("No session");
      const { data, error } = await client.auth.refreshSession();
      if (error || !data.session)
        throw error ?? new Error("Session refresh failed");
      const verified = await client.auth.getUser();
      if (verified.error || !verified.data.user) {
        throw verified.error ?? new Error("Session verification failed");
      }
      if (mounted) setReady(true);
    };

    setReady(false);
    verifySession().catch(() => {
      if (mounted)
        router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    });
    const { data: subscription } = client.auth.onAuthStateChange(
      (event, session) => {
        if (event === "SIGNED_OUT" || !session) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        }
      },
    );
    return () => {
      mounted = false;
      subscription.subscription.unsubscribe();
    };
  }, [pathname, router]);

  if (!ready) return <main aria-busy="true" />;
  return <>{children}</>;
}
