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
    supabase.auth.getSession()
      .then(({ data: { session } }) => {
        if (!mounted) return;
        if (!session) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        else setReady(true);
      })
      .catch(() => router.replace(`/login?next=${encodeURIComponent(pathname)}`));
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      else if (mounted) setReady(true);
    });
    return () => { mounted = false; subscription.subscription.unsubscribe(); };
  }, [pathname, router]);

  if (!ready) return <main aria-busy="true" />;
  return <>{children}</>;
}
