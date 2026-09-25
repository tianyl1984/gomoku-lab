<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { getGame, watchGame } from '../api/games'
import AgentGuide from '../components/AgentGuide.vue'
import GomokuBoard from '../components/GomokuBoard.vue'
import { COLOR_NAME, endReasonText, formatDuration, isOver } from '../utils/game'
import { pointLabel } from '../utils/notation'

const props = defineProps({
  id: { type: String, required: true },
})

const CONNECTION_LABEL = {
  connecting: '连接中…',
  open: '实时',
  reconnecting: '重连中…',
  closed: '已结束',
}

const game = ref(null)
const error = ref('')
const connection = ref('connecting')
const showNumbers = ref(false)
const copied = ref(false)
const historyRef = ref(null)
// 服务器时间 - 本地时间，用于校准倒计时
const clockOffset = ref(0)
const now = ref(Date.now())
let lastSeq = -1
let unwatch = null

function apply(event) {
  if (event.seq < lastSeq) return
  lastSeq = event.seq
  game.value = event.state
  // now 与 offset 必须取自同一时刻，否则倒计时会短暂超出上限
  now.value = Date.now()
  clockOffset.value = Date.parse(event.state.server_time) - now.value
}

async function load(id) {
  unwatch?.()
  unwatch = null
  game.value = null
  error.value = ''
  lastSeq = -1
  connection.value = 'connecting'
  try {
    // 先用 HTTP 取一次：EventSource 拿不到 404 等状态码
    apply({ seq: -1, state: await getGame(id) })
  } catch (e) {
    error.value = e.status === 404 ? '对局不存在（后端重启后内存中的对局会丢失）' : e.message
    connection.value = 'closed'
    return
  }
  unwatch = watchGame(id, {
    onEvent: apply,
    onStatus: (s) => (connection.value = s),
  })
}

watch(() => props.id, load, { immediate: true })

const ticker = setInterval(() => (now.value = Date.now()), 250)
onUnmounted(() => {
  unwatch?.()
  clearInterval(ticker)
})

const status = computed(() => game.value?.status)
const over = computed(() => isOver(status.value))
const seated = computed(() =>
  game.value ? ['black', 'white'].filter((c) => game.value.players[c]).length : 0,
)

const remainingMs = computed(() => {
  const deadline = game.value?.turn_deadline
  if (!deadline) return null
  const ms = Date.parse(deadline) - (now.value + clockOffset.value)
  return Math.min(Math.max(0, ms), game.value.move_timeout_seconds * 1000)
})

const headline = computed(() => {
  const g = game.value
  if (!g) return ''
  if (g.status === 'waiting') return `等待 agent 加入（${seated.value}/2）`
  if (g.status === 'playing') return `轮到${COLOR_NAME[g.current_player]}落子`
  return g.winner ? `${COLOR_NAME[g.winner]}胜` : '平局'
})

const headlineColor = computed(() => {
  const g = game.value
  if (!g) return null
  return g.status === 'playing' ? g.current_player : g.winner
})

async function copyLink() {
  try {
    await navigator.clipboard.writeText(window.location.href)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // 剪贴板不可用时用户可直接复制地址栏
  }
}

watch(
  () => game.value?.moves.length,
  async () => {
    await nextTick()
    const el = historyRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
)
</script>

<template>
  <section>
    <div class="topbar">
      <div class="title">
        对局 <code>{{ id }}</code>
        <button type="button" class="small" @click="copyLink">{{ copied ? '已复制' : '复制观战链接' }}</button>
      </div>
      <span class="conn" :class="connection">{{ CONNECTION_LABEL[connection] }}</span>
    </div>

    <p v-if="error" class="error" role="alert">
      {{ error }} · <RouterLink to="/">返回大厅</RouterLink>
    </p>

    <div v-if="game" class="layout">
      <div class="board-wrap">
        <GomokuBoard
          :size="game.size"
          :board="game.board"
          :moves="game.moves"
          :winning-line="game.winning_line"
          :show-numbers="showNumbers"
        />
      </div>

      <aside class="panel">
        <div class="card status" :class="{ over }">
          <div class="headline">
            <span v-if="headlineColor" class="chip" :class="headlineColor" />
            {{ headline }}
          </div>
          <div v-if="over" class="reason">{{ endReasonText(game) }}</div>
        </div>

        <div class="card players">
          <div
            v-for="color in ['black', 'white']"
            :key="color"
            class="player"
            :class="{ active: game.current_player === color, winner: game.winner === color }"
          >
            <span class="chip" :class="color" />
            <span class="name">
              <template v-if="game.players[color]">{{ game.players[color].name }}</template>
              <span v-else class="muted">等待加入…</span>
            </span>
            <span v-if="game.current_player === color && remainingMs !== null" class="clock" :class="{ low: remainingMs < 20000 }">
              {{ formatDuration(remainingMs) }}
            </span>
            <span v-else-if="game.winner === color" class="badge">胜</span>
          </div>
        </div>

        <label class="toggle">
          <input v-model="showNumbers" type="checkbox" />
          显示手数
        </label>

        <div class="history">
          <h2>棋谱 · {{ game.moves.length }} 手</h2>
          <ol v-if="game.moves.length" ref="historyRef">
            <li v-for="(m, i) in game.moves" :key="i">
              <span class="chip small" :class="m.color" />
              {{ game.players[m.color]?.name ?? COLOR_NAME[m.color] }}
              <code>{{ pointLabel(m.x, m.y, game.size) }}</code>
              <span class="coord">({{ m.x }}, {{ m.y }})</span>
            </li>
          </ol>
          <p v-else class="muted empty">{{ { waiting: '尚未开始', playing: '等待黑方第一手' }[status] ?? '无落子' }}</p>
        </div>
      </aside>
    </div>

    <details v-if="game" class="card guide" :open="status === 'waiting'">
      <summary>Agent 接入方式</summary>
      <AgentGuide :game-id="id" />
    </details>
  </section>
</template>

<style scoped>
.topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
}
button.small {
  padding: 0.15rem 0.6rem;
  font-size: 0.85rem;
  font-weight: normal;
}
.conn {
  font-size: 0.85rem;
  color: var(--text-muted);
}
.conn::before {
  content: '●';
  margin-right: 0.3rem;
}
.conn.open::before {
  color: var(--ok);
}
.conn.connecting::before,
.conn.reconnecting::before {
  color: var(--warn);
}
.error {
  margin-bottom: 1rem;
}
.layout {
  display: flex;
  gap: 1.5rem;
  align-items: flex-start;
}
.board-wrap {
  flex: 1 1 auto;
  max-width: 720px;
  min-width: 0;
}
.panel {
  flex: 0 0 300px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}
.headline {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 1.15rem;
  font-weight: 600;
}
.status.over {
  border-color: var(--accent);
}
.status.over .headline {
  color: var(--accent);
}
.reason {
  margin-top: 0.2rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}
.players {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.5rem 0.6rem;
}
.player {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
}
.player.active {
  background: var(--code-bg);
  font-weight: 600;
}
.player .name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.clock {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-variant-numeric: tabular-nums;
}
.clock.low {
  color: var(--error);
}
.badge {
  padding: 0 0.45rem;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
}
.toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.guide {
  margin-top: 1.25rem;
}
details summary {
  cursor: pointer;
  font-weight: 600;
}
details[open] summary {
  margin-bottom: 0.6rem;
}
.history h2 {
  margin: 0 0 0.4rem;
  font-size: 0.95rem;
  color: var(--text-muted);
}
.history ol {
  margin: 0;
  padding: 0.4rem 0 0.4rem 2.6rem;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  font-size: 0.9rem;
}
.history li {
  padding: 0.1rem 0;
}
.chip.small {
  width: 0.85em;
  height: 0.85em;
}
.coord {
  color: var(--text-muted);
  font-size: 0.8rem;
}
.empty {
  margin: 0;
  font-size: 0.9rem;
}
@media (max-width: 800px) {
  .layout {
    flex-direction: column;
  }
  .board-wrap,
  .panel {
    width: 100%;
    max-width: none;
    flex-basis: auto;
  }
}
</style>
