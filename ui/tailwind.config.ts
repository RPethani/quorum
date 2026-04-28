import type { Config } from "tailwindcss";

// Tailwind v4 reads its theme from CSS via the `@theme` directive in
// app/globals.css and components/design-system/tokens.css. This config file
// exists for tooling integration (IDE plugins, prettier-plugin-tailwindcss)
// and to declare which files contain Tailwind class usage.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
};

export default config;
