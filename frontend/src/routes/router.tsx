import { createBrowserRouter } from "react-router-dom"

import Home from "../pages/Home.jsx"
import NotFound from "../pages/NotFound.jsx"
import Login from "../pages/Login.tsx"
import Signup from "../pages/Signup.tsx"
import Dashboard from "../pages/Dashboard.tsx"
import ProtectedRoute from "../components/ProtectedRoute"

export const router = createBrowserRouter([
  { path: "/", element: <Home /> },
  { path: "/login", element: <Login /> },
  { path: "/signup", element: <Signup /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: "/dashboard", element: <Dashboard /> },
    ],
  },
  { path: "*", element: <NotFound /> },
])