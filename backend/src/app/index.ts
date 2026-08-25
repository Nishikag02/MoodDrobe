import express from 'express'
import type {Express} from 'express'

export function expressApp() :Express{
    const app = express();

    // Middleware


    // Routes
    app.get('/', (req, res) => {
        res.json({'message': 'Hello World!'});
    });



    return app;
}
