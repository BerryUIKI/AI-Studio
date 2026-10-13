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
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/tests/**"],
    rules: { "@typescript-eslint/no-explicit-any": "error" },
  },
  {
    files: ["src/components/**/*.tsx"],
    ignores: ["src/components/agent/CanvasAgentPrompt.tsx", "src/components/canvas/QuickAddMenu.tsx", "src/components/canvas/WorkspaceFrameNode.tsx", "src/components/canvas/InpaintModal.tsx"],
    rules: {
      "no-restricted-syntax": ["error", { selector: "JSXAttribute[name.name='style']", message: "Use Tailwind classes or the shared ProgressBar. Runtime canvas geometry exceptions are documented in docs/SERVICE_BOUNDARIES.md." }],
    },
  },
  {
    ignores: ["dist/**", "src-tauri/**", "node_modules/**"],
  },
];
