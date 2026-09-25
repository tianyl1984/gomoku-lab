<script setup>
import { onMounted, ref } from 'vue'
import { getHealth } from './api/client'

const status = ref('checking...')

onMounted(async () => {
  try {
    const data = await getHealth()
    status.value = data.status
  } catch (e) {
    status.value = `unreachable (${e.message})`
  }
})
</script>

<template>
  <main class="app">
    <h1>Gomoku Lab</h1>
    <p>Agent vs Agent 五子棋对战</p>
    <p>Backend: <code>{{ status }}</code></p>
  </main>
</template>

<style scoped>
.app {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1rem;
}
</style>
