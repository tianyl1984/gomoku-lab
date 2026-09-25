import { createRouter, createWebHistory } from 'vue-router'
import GameView from './views/GameView.vue'
import LobbyView from './views/LobbyView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'lobby', component: LobbyView },
    { path: '/games/:id', name: 'game', component: GameView, props: true },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
