import { createBrowserRouter } from "react-router-dom";

import Home from "../pages/Home.jsx";
import NotFound from "../pages/NotFound.jsx";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Home/>,
  },
  {
    path: "*",
    element: <NotFound />,
  },
]);