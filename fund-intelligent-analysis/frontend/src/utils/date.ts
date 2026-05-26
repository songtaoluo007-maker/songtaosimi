import dayjs from 'dayjs'

export function formatDate(date: string | Date, fmt = 'YYYY-MM-DD'): string {
  return dayjs(date).format(fmt)
}

export function formatTime(date: string | Date): string {
  return dayjs(date).format('MM-DD HH:mm')
}

export function shortTime(date: string | Date): string {
  return dayjs(date).format('HH:mm')
}

export function timeAgo(date: string | Date): string {
  const now = dayjs()
  const d = dayjs(date)
  const seconds = now.diff(d, 'second')
  if (seconds < 60) return '刚刚'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}小时前`
  return formatDate(date)
}

export function isToday(date: string | Date): boolean {
  return dayjs(date).isSame(dayjs(), 'day')
}

export function todayStr(): string {
  return dayjs().format('YYYY-MM-DD')
}
