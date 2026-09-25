// 棋盘记谱：列用字母 A 起，行号自下而上从 1 起（与棋盘边缘标注一致）
export const colLabel = (x) => String.fromCharCode(65 + x)
export const rowLabel = (y, size) => String(size - y)
export const pointLabel = (x, y, size) => `${colLabel(x)}${rowLabel(y, size)}`
