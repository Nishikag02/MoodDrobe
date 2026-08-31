import express from 'express'
import cors from 'cors'
import type {Express} from 'express'
import { toNodeHandler } from "better-auth/node";
import { auth } from "../lib/auth.js";

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

    app.use(express.json());

    // Routes
    app.get('/', (req, res) => {
        res.json({'message': 'Hello World!'});
    });


    return app;
}
