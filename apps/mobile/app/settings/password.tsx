import { useState } from "react";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { TextField } from "@/ui/TextField";

/** Change password (full accounts). Other sessions are signed out by the server. */
export default function ChangePasswordScreen() {
  const { changePassword } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: "info" | "error" } | null>(null);
  const mismatch = confirm.length > 0 && confirm !== next;

  const submit = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setMessage({ text: strings.settings.password.done, tone: "info" });
    } catch (e) {
      setMessage({ text: errorMessage(e), tone: "error" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen
      footer={
        <Button
          label={strings.settings.password.title}
          onPress={submit}
          loading={busy}
          disabled={!current || !next || next !== confirm}
        />
      }
    >
      <BackHeader title={strings.settings.password.title} />
      {message ? <Banner message={message.text} tone={message.tone} /> : null}
      <TextField
        label={strings.settings.password.current}
        value={current}
        onChangeText={setCurrent}
        secureTextEntry
        autoComplete="current-password"
        textContentType="password"
      />
      <TextField
        label={strings.settings.password.next}
        value={next}
        onChangeText={setNext}
        secureTextEntry
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <TextField
        label={strings.settings.password.confirm}
        value={confirm}
        onChangeText={setConfirm}
        secureTextEntry
        autoComplete="new-password"
        error={mismatch ? strings.settings.password.mismatch : null}
      />
    </Screen>
  );
}
