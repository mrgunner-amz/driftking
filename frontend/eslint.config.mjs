// eslint-config-next 16 ships native flat configs, so no eslintrc compat shim
// is needed. Two pins are load-bearing here: ESLint stays on 9.x (the react
// plugin bundled with eslint-config-next is not ESLint 10 compatible) and
// TypeScript stays on 6.x (typescript-eslint does not support TS 7 yet).
import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const eslintConfig = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...coreWebVitals,
  ...typescript,
];

export default eslintConfig;
