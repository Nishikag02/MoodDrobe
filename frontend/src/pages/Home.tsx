import { Link } from "react-router-dom"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export default function Home() {
  return (
    <div className="flex min-h-svh w-full flex-col items-center justify-center gap-6 p-6 md:p-10">
      <h1 className="text-2xl font-bold">Welcome to the Home Page</h1>
      <div className="flex gap-4">
        <Link to="/login" className={cn(buttonVariants({ variant: "outline" }))}>
          Login
        </Link>
        <Link to="/signup" className={cn(buttonVariants())}>
          Sign up
        </Link>
      </div>
    </div>
  )
}