import { authClient } from "./auth-client"

/** Signed-in user, or null. Never throws when the auth backend is down. */
export function useCurrentUser() {
  const { data } = authClient.useSession()
  return data?.user ?? null
}
