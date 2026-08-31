import { createAuthClient } from "better-auth/react"

export const authClient = createAuthClient({
  baseURL: import.meta.env.VITE_BACKEND_APP_URL,
})

export const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: `${import.meta.env.VITE_FRONTEND_APP_URL}/dashboard`,
      errorCallbackURL: `${import.meta.env.VITE_FRONTEND_APP_URL}/signup`,
    })
  }