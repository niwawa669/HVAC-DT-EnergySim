declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// 注意：此处曾用 `declare module '@/views/*'` 之类通配声明把所有目录退化为 any，
// 使类型检查形同虚设（vue-tsc 永远通过）。已移除，改为依赖真实模块解析。
// 若某个第三方包缺类型，请为其单独写 *.d.ts，而不是再次引入通配声明。
