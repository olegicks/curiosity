import * as SecureStore from "expo-secure-store";

import type { TokenStore } from "@/api/client";
import type { Tokens } from "@/api/types";

const KEY = "curiosity.session";

/**
 * Tokens live in the OS keychain/keystore (docs/spec/09 §9.1), mirrored in memory
 * so the API client can read them synchronously.
 */
export function createSecureTokenStore(): TokenStore & { load(): Promise<Tokens | null> } {
  let current: Tokens | null = null;
  return {
    get: () => current,
    async set(tokens) {
      current = tokens;
      if (tokens) await SecureStore.setItemAsync(KEY, JSON.stringify(tokens));
      else await SecureStore.deleteItemAsync(KEY);
    },
    async load() {
      try {
        const raw = await SecureStore.getItemAsync(KEY);
        current = raw ? (JSON.parse(raw) as Tokens) : null;
      } catch {
        current = null;
      }
      return current;
    },
  };
}
