import express from 'express'
import cors from 'cors'
import type {Express} from 'express'
import { toNodeHandler } from "better-auth/node";
import { auth } from "../lib/auth.js";
import { recommendationsRouter } from "./routes/recommendations.js";

export function expressApp() :Express{
    const app = express();

    app.use(
  cors({
    origin: "http://localhost:5173", // your Vite frontend's exact origin
    methods: ["GET", "POST", "PUT", "DELETE"],
    credentials: true, // required — allows cookies to be sent cross-origin
  })
)
    // Middleware
    app.all('/api/auth/{*any}', toNodeHandler(auth));

    // Before express.json(): the image route reads the raw request body itself.
    app.use('/api/recommendations', recommendationsRouter);

    app.use(express.json());

    // Routes
    app.get('/', (req, res) => {
        res.json({'message': 'Hello World!'});
    });


    return app;
}
