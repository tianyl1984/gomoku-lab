<template>
  <div class="app">
    <header class="header">
      <RouterLink to="/" class="brand">Gomoku Lab</RouterLink>
      <span class="subtitle">Agent 对战五子棋 · 观战</span>
    </header>
    <RouterView />
  </div>
</template>

<style scoped>
.app {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.25rem 1rem 3rem;
}
.header {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.25rem 0.75rem;
  margin-bottom: 1.25rem;
}
.brand {
  font-size: 1.5rem;
  font-weight: 700;
  color: inherit;
  text-decoration: none;
}
.subtitle {
  color: var(--text-muted);
}
</style>
