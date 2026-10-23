import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { SubjectGrid } from "@/features/subjects/SubjectGrid";
import { useSubject } from "@/features/subjects/SubjectProvider";
import { activeSubject } from "@/features/subjects/subjects";
import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";

/** Subject switcher, opened from the path header (D-17). */
export default function SubjectsScreen() {
  const { api } = useAuth();
  const { stored, choose } = useSubject();
  const subjects = useQuery({ queryKey: ["subjects"], queryFn: api.content.subjects });
  const items = subjects.data?.items ?? [];
  const current = activeSubject(items, stored);

  return (
    <Screen footer={<Button label={strings.subjects.done} onPress={() => router.back()} />}>
      <BackHeader title={strings.subjects.switchTitle} />
      <Text tone="muted">{strings.subjects.switchHint}</Text>
      {subjects.isPending ? <LoadingBlocks count={4} /> : null}
      {subjects.isError ? (
        <ErrorState
          message={errorMessage(subjects.error)}
          onRetry={() => void subjects.refetch()}
        />
      ) : null}
      {items.length > 0 ? (
        <SubjectGrid
          subjects={items}
          selected={current?.slug ?? null}
          onSelect={(slug) => {
            choose(slug);
            router.back();
          }}
        />
      ) : null}
    </Screen>
  );
}
