import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTs,
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts", "src/lib/api/schema.d.ts"] },
  {
    rules: {
      "react/no-danger": "error",
      "no-restricted-globals": ["error", { name: "localStorage", message: "No web storage (tokens live in memory)." }, { name: "sessionStorage", message: "No web storage." }],
    },
  },
];
export default config;
