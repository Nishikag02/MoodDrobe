import express from 'express'
import type {Express} from 'express'
import { toNodeHandler } from "better-auth/node";
import { auth } from "../lib/auth.js";

export function expressApp() :Express{
    const app = express();

    // Middleware
    app.all('/api/auth/{*any}', toNodeHandler(auth));

    app.use(express.json());

    // Routes
    app.get('/', (req, res) => {
        res.json({'message': 'Hello World!'});
    });


    return app;
}
