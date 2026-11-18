import { SiteHeader } from "@/components/mood/SiteHeader"
import { SignupForm } from "@/components/signup-form"

export default function Signup() {
  return (
    <div className="mood min-h-svh">
      <SiteHeader />
      <div className="flex w-full items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm md:max-w-3xl">
        <SignupForm />
      </div>
      </div>
    </div>
  )
}
