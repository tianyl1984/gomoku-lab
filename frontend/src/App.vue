<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { createGame, getGame, playMove } from './api/games'
import GomokuBoard from './components/GomokuBoard.vue'
import { pointLabel } from './utils/notation'

const GAME_KEY = 'gomoku-lab:game-id'
const PLAYER_NAME = { black: '黑方', white: '白方' }
const STATUS_TEXT = { black_win: '黑方胜', white_win: '白方胜', draw: '平局' }

const game = ref(null)
const pending = ref(false)
const error = ref('')
const size = ref(15)
const showNumbers = ref(false)
const historyRef = ref(null)

const playing = computed(() => game.value?.status === 'playing')

const statusText = computed(() => {
  const g = game.value
  if (!g) return '加载中…'
  return playing.value ? `轮到${PLAYER_NAME[g.current_player]}落子` : STATUS_TEXT[g.status]
})

// 当前指示的棋子颜色：对局中为行棋方，结束后为胜方
const statusStone = computed(() => {
  const g = game.value
  if (!g) return null
  return playing.value ? g.current_player : g.winner
})

function saveGameId(id) {
  try {
    sessionStorage.setItem(GAME_KEY, id)
  } catch {
    // 存储不可用时只是刷新后不能恢复对局
  }
}

function loadGameId() {
  try {
    return sessionStorage.getItem(GAME_KEY)
  } catch {
    return null
  }
}

async function run(fn) {
  pending.value = true
  error.value = ''
  try {
    await fn()
  } catch (e) {
    error.value = e.status === 404 ? '对局不存在（后端可能已重启），请新开一局' : e.message
  } finally {
    pending.value = false
  }
}

function newGame() {
  return run(async () => {
    game.value = await createGame({ size: size.value })
    saveGameId(game.value.id)
  })
}

function onPlace({ x, y }) {
  const g = game.value
  if (!g || !playing.value || pending.value) return
  run(async () => {
    game.value = await playMove(g.id, x, y, g.current_player)
  })
}

watch(
  () => game.value?.moves.length,
  async () => {
    await nextTick()
    const el = historyRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

onMounted(async () => {
  const savedId = loadGameId()
  if (savedId) {
    try {
      game.value = await getGame(savedId)
      size.value = game.value.size
      return
    } catch {
      // 旧对局已不在内存中，新建一局
    }
  }
  await newGame()
})
</script>

<template>
  <main class="app">
    <header class="header">
      <h1>Gomoku Lab</h1>
      <p class="subtitle">五子棋规则验证 · 人工对弈模式</p>
    </header>

    <div class="layout">
      <section class="board-wrap">
        <GomokuBoard
          v-if="game"
          :size="game.size"
          :board="game.board"
          :moves="game.moves"
          :winning-line="game.winning_line"
          :current-player="game.current_player"
          :interactive="playing && !pending"
          :show-numbers="showNumbers"
          @place="onPlace"
        />
      </section>

      <aside class="panel">
        <div class="status" :class="{ over: game && !playing }">
          <span v-if="statusStone" class="chip" :class="statusStone" />
          <span>{{ statusText }}</span>
        </div>

        <p v-if="error" class="error" role="alert">{{ error }}</p>

        <div class="controls">
          <label>
            棋盘
            <select v-model.number="size" :disabled="pending">
              <option :value="15">15 × 15</option>
              <option :value="19">19 × 19</option>
            </select>
          </label>
          <button type="button" :disabled="pending" @click="newGame">新开一局</button>
          <label class="toggle">
            <input v-model="showNumbers" type="checkbox" />
            显示手数
          </label>
        </div>

        <div v-if="game" class="history">
          <h2>棋谱 · {{ game.moves.length }} 手</h2>
          <ol ref="historyRef">
            <li v-for="(m, i) in game.moves" :key="i">
              <span class="chip small" :class="m.player" />
              {{ PLAYER_NAME[m.player] }}
              <code>{{ pointLabel(m.x, m.y, game.size) }}</code>
              <span class="coord">({{ m.x }}, {{ m.y }})</span>
            </li>
          </ol>
          <p v-if="!game.moves.length" class="empty">黑方先行，点击棋盘落子</p>
        </div>

        <p v-if="game" class="meta">对局 ID <code>{{ game.id }}</code></p>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.app {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}
.header h1 {
  margin: 0;
  font-size: 1.6rem;
}
.subtitle {
  margin: 0.25rem 0 1.25rem;
  color: var(--text-muted);
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
  flex: 0 0 280px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.status {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.8rem 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  font-size: 1.15rem;
  font-weight: 600;
}
.status.over {
  border-color: var(--accent);
  color: var(--accent);
}
.chip {
  display: inline-block;
  width: 1.1em;
  height: 1.1em;
  border-radius: 50%;
  flex: none;
}
.chip.small {
  width: 0.85em;
  height: 0.85em;
  vertical-align: -0.05em;
}
.chip.black {
  background: radial-gradient(circle at 35% 35%, #6b6b6b, #111);
}
.chip.white {
  background: radial-gradient(circle at 35% 35%, #fff, #d4d4d4);
  box-shadow: inset 0 0 0 1px #9e9e9e;
}
.error {
  margin: 0;
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  background: var(--error-bg);
  color: var(--error);
  font-size: 0.9rem;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}
.controls label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
select,
button {
  font: inherit;
  padding: 0.35rem 0.7rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: inherit;
}
button {
  cursor: pointer;
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
button:disabled {
  opacity: 0.6;
  cursor: default;
}
.history h2 {
  margin: 0 0 0.4rem;
  font-size: 0.95rem;
  color: var(--text-muted);
}
.history ol {
  margin: 0;
  padding: 0.4rem 0 0.4rem 2.6rem;
  max-height: 340px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  font-size: 0.9rem;
}
.history li {
  padding: 0.1rem 0;
}
.coord {
  color: var(--text-muted);
  font-size: 0.8rem;
}
.empty {
  margin: 0.5rem 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}
.meta {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.8rem;
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
