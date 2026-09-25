<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createGame } from '../api/games'

const router = useRouter()
const error = ref('')

// 进入首页即新建一局（15 × 15），用 replace 跳转，避免后退回首页时又创建一局
async function newGame() {
  error.value = ''
  try {
    const game = await createGame()
    router.replace({ name: 'game', params: { id: game.id } })
  } catch (e) {
    error.value = `创建对局失败：${e.message}`
  }
}

onMounted(newGame)
</script>

<template>
  <section class="card">
    <template v-if="error">
      <p class="error" role="alert">{{ error }}</p>
      <button type="button" class="primary" @click="newGame">重试</button>
    </template>
    <p v-else class="muted">正在创建对局…</p>
  </section>
</template>

<style scoped>
p {
  margin: 0 0 0.75rem;
}
p:last-child {
  margin: 0;
}
</style>
