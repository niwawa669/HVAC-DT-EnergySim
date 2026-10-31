// format.js 的类型声明（该文件为 JS，保留实现不动，此处补类型）
export function formatNumber(num: number | null | undefined): string
export function formatDate(date: string | Date): string
export function formatTime(seconds: number): string
export function formatEnergy(value: number): string
export function formatTemperature(value: number | null | undefined): string
export function formatPercentage(value: number): string
export function truncateText(text: string, length?: number): string
export function parseCSV(content: string): Record<string, string>[]
export function downloadFile(content: string, filename: string): void
