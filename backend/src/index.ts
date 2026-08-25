import 'dotenv/config';
import {createServer} from "node:http";
import {expressApp} from "./app/index.js";

async function main(){
try {
    const server = createServer(expressApp());
    const PORT: number = process.env.PORT ? parseInt(process.env.PORT) : 3000;


    server.listen(PORT, () => {
        console.log(`Server is running on port ${PORT}`);
    });


} catch (error) {
    console.log('Error starting http server',error);
    throw error;
}
}


main();