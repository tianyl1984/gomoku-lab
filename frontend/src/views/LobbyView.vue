<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createGame, listGames } from '../api/games'
import { STATUS_LABEL } from '../utils/game'

const POLL_MS = 3000

const router = useRouter()
const games = ref([])
const size = ref(15)
const creating = ref(false)
const error = ref('')
let timer

async function refresh() {
  try {
    games.value = await listGames()
    error.value = ''
  } catch (e) {
    error.value = `无法获取对局列表：${e.message}`
  }
}

async function newGame() {
  creating.value = true
  error.value = ''
  try {
    const game = await createGame({ size: size.value })
    router.push({ name: 'game', params: { id: game.id } })
  } catch (e) {
    error.value = e.message
    creating.value = false
  }
}

const formatTime = (iso) => new Date(iso).toLocaleTimeString()

onMounted(() => {
  refresh()
  timer = setInterval(refresh, POLL_MS)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <section class="lobby">
    <div class="card create">
      <div>
        <h2>新开一局</h2>
        <p class="muted">创建后把对局链接或 ID 发给两个 agent，它们加入后自动开赛。</p>
      </div>
      <div class="create-controls">
        <select v-model.number="size" :disabled="creating" aria-label="棋盘大小">
          <option :value="15">15 × 15</option>
          <option :value="19">19 × 19</option>
        </select>
        <button type="button" class="primary" :disabled="creating" @click="newGame">创建对局</button>
      </div>
    </div>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <h2>对局列表</h2>
    <p v-if="!games.length" class="muted">暂无对局。后端重启后内存中的对局会清空。</p>
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>对局</th>
            <th>状态</th>
            <th>黑方</th>
            <th>白方</th>
            <th>手数</th>
            <th>创建时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="g in games" :key="g.id">
            <td>
              <RouterLink :to="{ name: 'game', params: { id: g.id } }">
                <code>{{ g.id }}</code>
              </RouterLink>
            </td>
            <td><span class="status" :class="g.status">{{ STATUS_LABEL[g.status] }}</span></td>
            <td>{{ g.players.black?.name ?? '—' }}</td>
            <td>{{ g.players.white?.name ?? '—' }}</td>
            <td>{{ g.move_count }}</td>
            <td class="muted">{{ formatTime(g.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
h2 {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
}
.lobby {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.create {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.create p {
  margin: 0;
}
.create-controls {
  display: flex;
  gap: 0.5rem;
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}
th,
td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  white-space: nowrap;
}
th {
  color: var(--text-muted);
  font-weight: 600;
  border-bottom: 1px solid var(--border);
}
tbody tr + tr td {
  border-top: 1px solid var(--border);
}
.status.playing {
  color: var(--ok);
  font-weight: 600;
}
.status.waiting {
  color: var(--warn);
}
</style>
