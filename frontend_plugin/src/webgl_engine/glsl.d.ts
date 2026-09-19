/**
 * @file glsl.d.ts
 * @brief TypeScript 模块声明 —— 使 .glsl 文件可作为字符串导入
 *
 * 搭配 webpack/vite 的 raw-loader 或 esbuild 的 text loader 使用。
 * 在 tsconfig.json 的 "include" 范围内自动生效。
 */
declare module "*.glsl" {
  const value: string;
  export default value;
}
