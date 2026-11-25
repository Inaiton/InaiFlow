import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTs,
  { ignores: [".next/**", "node_modules/**", "src/lib/api/schema.d.ts", "next-env.d.ts"] },
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": ["warn", { fixStyle: "inline-type-imports" }],
      "react/no-danger": "error",
      "no-restricted-globals": ["error", { name: "localStorage", message: "Never persist tokens in web storage." }, { name: "sessionStorage", message: "Never persist tokens in web storage." }],
    },
  },
];

export default config;
