declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// 声明所有 @/ 路径下的模块为 any 类型（快速解决）
declare module '@/views/*' {
  const content: any
  export default content
}

declare module '@/components/*' {
  const content: any
  export default content
}

declare module '@/components/layout/*' {
  const content: any
  export default content
}

declare module '@/stores/*' {
  const content: any
  export default content
}

declare module '@/utils/*' {
  const content: any
  export default content
}

declare module '@/composables/*' {
  const content: any
  export default content
}

declare module '@/api/*' {
  const content: any
  export default content
}

declare module '@/mocks/*' {
  const content: any
  export default content
}
