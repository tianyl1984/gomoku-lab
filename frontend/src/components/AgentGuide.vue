<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  gameId: { type: String, required: true },
})

// 服务器地址取自地址栏：前端与 /api 同源（开发时由 Vite 代理到后端）
const origin = window.location.origin
const ruleUrl = `${origin}/api/game_rule.md`

const prompt = computed(
  () =>
    `请作为五子棋 agent 参加 Gomoku Lab 对战：服务器地址 ${origin}，对局 ID ${props.gameId}；` +
    `先阅读 ${ruleUrl} 了解对战规则与接入协议，然后在本地生成 secret 申请加入该对局，` +
    `通过 SSE 监听对局事件，轮到你时通过 HTTP 落子，直到对局结束。`,
)

const copied = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(prompt.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // 非安全上下文下剪贴板不可用，用户可手动选择复制
  }
}
</script>

<template>
  <div class="guide">
    <p class="muted">
      把下面的提示词分别发给两个 agent，它们加入后自动开赛。规则与协议详见
      <a :href="ruleUrl" target="_blank" rel="noopener">game_rule.md</a>。
    </p>
    <div class="prompt">
      <p>{{ prompt }}</p>
      <button type="button" class="primary" @click="copy">{{ copied ? '已复制' : '复制提示词' }}</button>
    </div>
  </div>
</template>

<style scoped>
.guide > p {
  margin: 0 0 0.6rem;
  font-size: 0.88rem;
}
.prompt {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 6px;
  background: var(--code-bg);
}
.prompt p {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.prompt button {
  flex: none;
}
@media (max-width: 600px) {
  .prompt {
    flex-direction: column;
  }
}
</style>
