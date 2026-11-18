import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "../db/schema.js";

const db = drizzle(new Pool({ connectionString: process.env.DATABASE_URL }), {
  schema,
});

export const auth = betterAuth({
  database: drizzleAdapter(db, { provider: "pg", schema }),
  baseURL: "http://localhost:3000",
  // localhost for development; *.trycloudflare.com for the public showcase tunnel
  // (the quick-tunnel URL changes on every restart). Add more with
  // EXTRA_TRUSTED_ORIGINS=https://a.example,https://b.example in backend/.env.
  trustedOrigins: [
    "http://localhost:5173",
    "https://*.trycloudflare.com",
    ...(process.env.EXTRA_TRUSTED_ORIGINS ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  ],
  emailAndPassword: { enabled: true }, 
  socialProviders:{
    google: { 
            clientId: process.env.GOOGLE_CLIENT_ID!, 
            clientSecret: process.env.GOOGLE_CLIENT_SECRET!, 
        }, 
  }
});
