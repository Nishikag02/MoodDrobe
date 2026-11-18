import { createBrowserRouter } from "react-router-dom"

import Studio from "../pages/Studio.tsx"
import Saved from "../pages/Saved.tsx"
import Pinboard from "../pages/Pinboard.tsx"
import Home from "../pages/Home.jsx"
import NotFound from "../pages/NotFound.jsx"
import Login from "../pages/Login.tsx"
import Signup from "../pages/Signup.tsx"
import Dashboard from "../pages/Dashboard.tsx"
import ProtectedRoute from "../components/ProtectedRoute"

export const router = createBrowserRouter([
  { path: "/", element: <Studio /> },
  { path: "/saved", element: <Saved /> },
  { path: "/pinboard", element: <Pinboard /> },
  { path: "/welcome", element: <Home /> },
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