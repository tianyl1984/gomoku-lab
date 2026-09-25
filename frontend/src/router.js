import { createRouter, createWebHistory } from 'vue-router'
import GameView from './views/GameView.vue'
import HomeView from './views/HomeView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/games/:id', name: 'game', component: GameView, props: true },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
