const STATUS_META = {
  pending: { label: '未开始', type: 'info' },
  warning: { label: '待完善', type: 'warning' },
  blocked: { label: '待处理', type: 'danger' },
  ready: { label: '可执行', type: 'primary' },
  completed: { label: '已完成', type: 'success' },
  optional: { label: '可选功能', type: 'info' },
}

export const getPrecheckStatusLabel = (status) =>
  STATUS_META[status]?.label || '待确认'

export const getPrecheckStatusType = (status) =>
  STATUS_META[status]?.type || 'info'
