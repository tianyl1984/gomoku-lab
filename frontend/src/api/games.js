import { request } from './client'

export const createGame = (options = {}) => request('/games', { method: 'POST', body: options })

export const getGame = (id) => request(`/games/${id}`)

export const playMove = (id, x, y, player) =>
  request(`/games/${id}/moves`, { method: 'POST', body: { x, y, player } })
