<script setup>
import { computed, ref } from 'vue'
import { colLabel, rowLabel } from '../utils/notation'

const props = defineProps({
  size: { type: Number, required: true },
  // board[y][x]：0 空，1 黑，2 白
  board: { type: Array, required: true },
  moves: { type: Array, default: () => [] },
  winningLine: { type: Array, default: null },
  currentPlayer: { type: String, default: 'black' },
  interactive: { type: Boolean, default: true },
  showNumbers: { type: Boolean, default: false },
})

const emit = defineEmits(['place'])

const CELL = 40
const MARGIN = 56
const STONE_R = CELL * 0.45
// 坐标标注离边缘的距离，需落在边线棋子之外
const LABEL_OFFSET = 20

const span = computed(() => CELL * (props.size - 1))
const viewSize = computed(() => span.value + MARGIN * 2)
const pos = (i) => MARGIN + i * CELL
const indices = computed(() => Array.from({ length: props.size }, (_, i) => i))

// 星位：19 路 9 个，13~18 路 5 个，其余奇数路只有天元
const starPoints = computed(() => {
  const n = props.size
  const c = Math.floor(n / 2)
  if (n >= 19) {
    const s = [3, c, n - 4]
    return s.flatMap((x) => s.map((y) => [x, y]))
  }
  if (n >= 13) return [[3, 3], [3, n - 4], [n - 4, 3], [n - 4, n - 4], [c, c]]
  return n % 2 === 1 ? [[c, c]] : []
})

const stones = computed(() => {
  const list = []
  props.board.forEach((row, y) =>
    row.forEach((v, x) => {
      if (v) list.push({ x, y, color: v === 1 ? 'black' : 'white' })
    }),
  )
  return list
})

const moveNumbers = computed(() => {
  const map = new Map()
  props.moves.forEach((m, i) => map.set(`${m.x},${m.y}`, i + 1))
  return map
})

const lastMove = computed(() => props.moves.at(-1) ?? null)

const winningEnds = computed(() => {
  const line = props.winningLine
  if (!line?.length) return null
  const [x1, y1] = line[0]
  const [x2, y2] = line.at(-1)
  return { x1: pos(x1), y1: pos(y1), x2: pos(x2), y2: pos(y2) }
})

const svgRef = ref(null)
const hover = ref(null)

// 屏幕坐标 → 最近的交叉点；超出棋盘返回 null
function toPoint(evt) {
  const svg = svgRef.value
  const ctm = svg?.getScreenCTM()
  if (!ctm) return null
  const pt = new DOMPoint(evt.clientX, evt.clientY).matrixTransform(ctm.inverse())
  const x = Math.round((pt.x - MARGIN) / CELL)
  const y = Math.round((pt.y - MARGIN) / CELL)
  if (x < 0 || y < 0 || x >= props.size || y >= props.size) return null
  return { x, y }
}

const isEmpty = (p) => p && props.board[p.y][p.x] === 0

function onMove(evt) {
  const p = props.interactive ? toPoint(evt) : null
  hover.value = isEmpty(p) ? p : null
}

function onClick(evt) {
  if (!props.interactive) return
  const p = toPoint(evt)
  if (isEmpty(p)) {
    hover.value = null
    emit('place', p)
  }
}
</script>

<template>
  <svg
    ref="svgRef"
    class="board"
    :class="{ interactive }"
    :viewBox="`0 0 ${viewSize} ${viewSize}`"
    role="img"
    aria-label="五子棋棋盘"
    @mousemove="onMove"
    @mouseleave="hover = null"
    @click="onClick"
  >
    <defs>
      <radialGradient id="stone-black" cx="35%" cy="35%" r="65%">
        <stop offset="0%" stop-color="#6b6b6b" />
        <stop offset="100%" stop-color="#111" />
      </radialGradient>
      <radialGradient id="stone-white" cx="35%" cy="35%" r="65%">
        <stop offset="0%" stop-color="#fff" />
        <stop offset="100%" stop-color="#d4d4d4" />
      </radialGradient>
    </defs>

    <rect class="wood" :width="viewSize" :height="viewSize" rx="8" />

    <g class="grid">
      <line
        v-for="i in indices"
        :key="`h${i}`"
        :x1="pos(0)"
        :y1="pos(i)"
        :x2="pos(size - 1)"
        :y2="pos(i)"
      />
      <line
        v-for="i in indices"
        :key="`v${i}`"
        :x1="pos(i)"
        :y1="pos(0)"
        :x2="pos(i)"
        :y2="pos(size - 1)"
      />
      <rect class="frame" :x="pos(0)" :y="pos(0)" :width="span" :height="span" />
      <circle v-for="[x, y] in starPoints" :key="`s${x},${y}`" class="star" :cx="pos(x)" :cy="pos(y)" r="4" />
    </g>

    <g class="labels">
      <text v-for="i in indices" :key="`c${i}`" :x="pos(i)" :y="LABEL_OFFSET">{{ colLabel(i) }}</text>
      <text v-for="i in indices" :key="`r${i}`" :x="LABEL_OFFSET" :y="pos(i)">{{ rowLabel(i, size) }}</text>
    </g>

    <circle
      v-if="hover"
      class="ghost"
      :cx="pos(hover.x)"
      :cy="pos(hover.y)"
      :r="STONE_R"
      :fill="`url(#stone-${currentPlayer})`"
    />

    <circle
      v-for="s in stones"
      :key="`${s.x},${s.y}`"
      class="stone"
      :class="s.color"
      :cx="pos(s.x)"
      :cy="pos(s.y)"
      :r="STONE_R"
      :fill="`url(#stone-${s.color})`"
    />

    <!-- 连线画在棋子之上、手数之下，避免遮挡手数 -->
    <line v-if="winningEnds" class="win-line" v-bind="winningEnds" />

    <template v-if="showNumbers">
      <text
        v-for="s in stones"
        :key="`n${s.x},${s.y}`"
        class="move-number"
        :class="[s.color, { last: lastMove && lastMove.x === s.x && lastMove.y === s.y }]"
        :x="pos(s.x)"
        :y="pos(s.y)"
      >
        {{ moveNumbers.get(`${s.x},${s.y}`) }}
      </text>
    </template>
    <circle
      v-else-if="lastMove"
      class="last-marker"
      :cx="pos(lastMove.x)"
      :cy="pos(lastMove.y)"
      :r="CELL * 0.1"
    />
  </svg>
</template>

<style scoped>
.board {
  display: block;
  width: 100%;
  height: auto;
  user-select: none;
}
.board.interactive {
  cursor: pointer;
}
.wood {
  fill: #dcb35c;
}
.grid line,
.grid .frame {
  stroke: #5b4520;
  stroke-width: 1;
  fill: none;
}
.grid .frame {
  stroke-width: 2;
}
.star {
  fill: #5b4520;
}
.labels text {
  fill: #5b4520;
  font-size: 14px;
  text-anchor: middle;
  dominant-baseline: central;
}
.stone.black {
  filter: drop-shadow(1px 2px 1.5px rgb(0 0 0 / 0.45));
}
.stone.white {
  stroke: #9e9e9e;
  stroke-width: 0.5;
  filter: drop-shadow(1px 2px 1.5px rgb(0 0 0 / 0.3));
}
.ghost {
  opacity: 0.45;
  pointer-events: none;
}
.move-number {
  font-size: 15px;
  font-weight: 600;
  text-anchor: middle;
  dominant-baseline: central;
  /* 以棋子底色描边，连线穿过时手数仍清晰 */
  paint-order: stroke;
  stroke-width: 4px;
  stroke-linejoin: round;
  pointer-events: none;
}
.move-number.black {
  fill: #fff;
  stroke: #1a1a1a;
}
.move-number.white {
  fill: #111;
  stroke: #f2f2f2;
}
.move-number.last {
  fill: #e53935;
}
.last-marker {
  fill: #e53935;
  pointer-events: none;
}
.win-line {
  stroke: #e53935;
  stroke-width: 4;
  stroke-linecap: round;
  opacity: 0.75;
  pointer-events: none;
}
</style>
