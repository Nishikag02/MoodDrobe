import { SiteHeader } from "@/components/mood/SiteHeader"
import { LoginForm } from "@/components/login-form"

export default function Login() {
  return (
    <div className="mood min-h-svh">
      <SiteHeader />
      <div className="flex w-full items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm md:max-w-3xl">
        <LoginForm />
      </div>
      </div>
    </div>
  )
}
