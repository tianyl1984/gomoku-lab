export const COLOR_NAME = { black: '黑方', white: '白方' }

export const STATUS_LABEL = {
  waiting: '等待加入',
  playing: '对战中',
  black_win: '黑方胜',
  white_win: '白方胜',
  draw: '平局',
}

export const isOver = (status) => ['black_win', 'white_win', 'draw'].includes(status)

export function endReasonText(state) {
  const loser = COLOR_NAME[state.winner === 'black' ? 'white' : 'black']
  switch (state.end_reason) {
    case 'five':
      return '连成五子'
    case 'timeout':
      return `${loser}超时未落子，判负`
    case 'invalid_moves':
      return `${loser}累计 ${state.max_invalid_moves} 次非法落子，判负`
    case 'board_full':
      return '棋盘已满'
    default:
      return ''
  }
}

export function formatDuration(ms) {
  const total = Math.ceil(ms / 1000)
  const m = String(Math.floor(total / 60)).padStart(2, '0')
  const s = String(total % 60).padStart(2, '0')
  return `${m}:${s}`
}
