import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "current-subject";

type SubjectContextValue = {
  /** The subject slug the learner picked on this device, if any. */
  stored: string | null;
  choose: (slug: string) => void;
};

const SubjectContext = createContext<SubjectContextValue | null>(null);

/** The chosen subject is a device preference, like the theme (D-17). */
export function SubjectProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState<string | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((value) => {
        if (value) setStored((current) => current ?? value);
      })
      .catch(() => undefined); // falls back to the first subject with lessons
  }, []);

  const value = useMemo<SubjectContextValue>(
    () => ({
      stored,
      choose: (slug) => {
        setStored(slug);
        AsyncStorage.setItem(STORAGE_KEY, slug).catch(() => undefined);
      },
    }),
    [stored],
  );

  return <SubjectContext.Provider value={value}>{children}</SubjectContext.Provider>;
}

export function useSubject(): SubjectContextValue {
  const value = useContext(SubjectContext);
  if (!value) throw new Error("useSubject must be used inside SubjectProvider");
  return value;
}
