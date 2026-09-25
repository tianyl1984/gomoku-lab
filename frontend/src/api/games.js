import { isOver } from '../utils/game'
import { request } from './client'

export const createGame = (options = {}) => request('/games', { method: 'POST', body: options })

export const listGames = () => request('/games')

export const getGame = (id) => request(`/games/${id}`)

const EVENT_TYPES = ['snapshot', 'player_joined', 'game_started', 'move', 'game_over']

/**
 * 通过 SSE 订阅对局。每个事件都携带完整 state，onEvent 直接用它替换本地状态即可。
 * 对局结束后主动关闭连接，避免 EventSource 在服务端关流后自动重连。
 * onStatus: 'open' | 'reconnecting' | 'closed'。返回取消订阅函数。
 */
export function watchGame(id, { onEvent, onStatus }) {
  const source = new EventSource(`/api/games/${id}/events`)
  const handle = (e) => {
    const event = JSON.parse(e.data)
    onEvent(event)
    if (event.type === 'game_over' || (event.type === 'snapshot' && isOver(event.state.status))) {
      source.close()
      onStatus?.('closed')
    }
  }
  EVENT_TYPES.forEach((type) => source.addEventListener(type, handle))
  source.onopen = () => onStatus?.('open')
  source.onerror = () =>
    onStatus?.(source.readyState === EventSource.CLOSED ? 'closed' : 'reconnecting')
  return () => source.close()
}
