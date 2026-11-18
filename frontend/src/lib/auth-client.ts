import { createAuthClient } from "better-auth/react"

// Same origin as the page: Vite proxies /api to Express, so login also works on the public tunnel URL.
export const authClient = createAuthClient({
  baseURL: window.location.origin,
})

export const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: `${window.location.origin}/dashboard`,
      errorCallbackURL: `${window.location.origin}/signup`,
    })
  }
