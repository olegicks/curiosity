import { router } from "expo-router";
import { useState } from "react";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { strings } from "@/i18n/en";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";

/** Guest -> full account (journey J5). The same user id keeps all progress. */
export default function CreateAccountScreen() {
  const { upgrade } = useAuth();
  const [email, setEmail] = useState("");
  const [confirmEmail, setConfirmEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A typo'd email would make password reset impossible (R-8), so ask twice.
  const mismatch =
    confirmEmail.length > 0 && email.trim().toLowerCase() !== confirmEmail.trim().toLowerCase();
  const ready = email.trim() && confirmEmail.trim() && password && !mismatch;

  const submit = async () => {
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      await upgrade(email.trim(), password, displayName.trim() || null);
      router.back();
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <Screen
      footer={
        <>
          <Button
            label={strings.createAccount.submit}
            onPress={submit}
            loading={busy}
            disabled={!ready}
          />
          <Button
            label={strings.createAccount.cancel}
            variant="ghost"
            onPress={() => router.back()}
          />
        </>
      }
    >
      <Text variant="title" accessibilityRole="header">
        {strings.createAccount.title}
      </Text>
      <Text tone="muted">{strings.createAccount.body}</Text>
      {error ? <Banner message={error} tone="error" /> : null}
      <TextField
        label={strings.createAccount.email}
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        textContentType="emailAddress"
      />
      <TextField
        label={strings.createAccount.confirmEmail}
        value={confirmEmail}
        onChangeText={setConfirmEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        error={mismatch ? strings.createAccount.emailsDiffer : null}
      />
      <TextField
        label={strings.createAccount.password}
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <TextField
        label={strings.createAccount.displayName}
        value={displayName}
        onChangeText={setDisplayName}
        maxLength={40}
        autoComplete="name"
      />
    </Screen>
  );
}
