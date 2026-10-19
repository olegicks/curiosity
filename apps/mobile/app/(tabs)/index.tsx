import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import type { Destination } from "@/features/discover/discover";
import { DiscoverView } from "@/features/discover/DiscoverView";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";

/** Discover home (docs/spec/02 §2.5): everything comes from one GET /discover call. */
export default function DiscoverScreen() {
  const { api, session } = useAuth();
  const discover = useQuery({ queryKey: ["discover"], queryFn: api.discover.get });
  const name = session.status === "signedIn" ? session.me.user.display_name : null;

  const navigate = (destination: Destination) => {
    switch (destination.kind) {
      case "review":
        router.push("/review");
        return;
      case "lesson":
        router.push({ pathname: "/lesson/[slug]", params: { slug: destination.slug } });
        return;
      case "play":
        router.push({ pathname: "/lesson/[slug]/play", params: { slug: destination.slug } });
        return;
      case "learn":
        router.push("/learn");
    }
  };

  return (
    <Screen refreshing={discover.isRefetching} onRefresh={() => void discover.refetch()}>
      {discover.isPending ? <LoadingBlocks count={4} /> : null}
      {discover.isError ? (
        <ErrorState
          message={errorMessage(discover.error)}
          onRetry={() => void discover.refetch()}
        />
      ) : null}
      {discover.data ? (
        <DiscoverView
          discover={discover.data}
          displayName={name}
          now={new Date()}
          onNavigate={navigate}
          onOpenProfile={() => router.push("/profile")}
        />
      ) : null}
    </Screen>
  );
}
