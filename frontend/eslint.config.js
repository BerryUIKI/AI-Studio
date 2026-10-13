import js from "@eslint/js";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "no-undef": "off",
      "no-empty": "warn",
    },
  },
  {
    files: ["src/api/**/*.{ts,tsx}", "src/types/**/*.ts", "src/stores/useCanvasStore.ts", "src/stores/useAgentStore.ts", "src/stores/useCreationSetupStore.ts"],
    rules: { "@typescript-eslint/no-explicit-any": "error" },
  },
  {
    ignores: ["dist/**", "src-tauri/**", "node_modules/**"],
  },
];
