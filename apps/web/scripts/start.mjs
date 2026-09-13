import { cpSync } from "node:fs";
import { fileURLToPath } from "node:url";
const root = new URL("../", import.meta.url);
cpSync(
  new URL(".next/static", root),
  new URL(".next/standalone/.next/static", root),
  { recursive: true },
);
process.env.HOSTNAME = process.env.HOSTNAME || "127.0.0.1";
process.env.PORT = process.env.PORT || "3000";
await import(fileURLToPath(new URL(".next/standalone/server.js", root)));
