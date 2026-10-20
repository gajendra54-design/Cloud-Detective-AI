import js from '@eslint/js';
import tseslint from 'typescript-eslint';
export default tseslint.config({ignores:['dist/**','node_modules/**']},js.configs.recommended,...tseslint.configs.recommended,{files:['src/**/*.{ts,tsx}'],rules:{'@typescript-eslint/no-unused-vars':'error','@typescript-eslint/no-explicit-any':'error'}});
