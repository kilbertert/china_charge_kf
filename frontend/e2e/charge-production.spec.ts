import { expect, test, type Page } from '@playwright/test'


async function sendAndRead(page: Page, text: string) {
  const replies = page.locator('.row.assistant .text:not(.typing)')
  const before = await replies.count()
  const startedAt = Date.now()
  await page.locator('textarea.input').fill(text)
  await page.getByRole('button', { name: '发送' }).click()
  await expect(replies).toHaveCount(before + 1)
  return {
    text: (await replies.nth(before).innerText()).trim(),
    elapsedMs: Date.now() - startedAt,
  }
}


test.beforeEach(async ({ page }) => {
  await page.goto('./')
  await page.evaluate(() => localStorage.removeItem('chat_session_id'))
  await page.reload()
})


test('已核实的计费和用户端报修事实在浏览器中直接返回', async ({ page }) => {
  const association = await sendAndRead(page, '如何给站点关联计费模板？')
  expect(association.elapsedMs).toBeLessThan(10_000)
  expect(association.text).toContain('我的场地')
  expect(association.text).toContain('计费设置')
  expect(association.text).toContain('不是关联模板的前置条件')

  const orderExport = await sendAndRead(page, 'PC后台订单怎么导出？')
  expect(orderExport.elapsedMs).toBeLessThan(10_000)
  expect(orderExport.text).toContain('财务 > 订单中心 > 充电桩订单 > 新能源车充电订单')
  expect(orderExport.text).toContain('当前查询结果')
  expect(orderExport.text).not.toContain('前置条件')

  const activation = await sendAndRead(page, '计费模板创建后就直接生效吗？')
  expect(activation.elapsedMs).toBeLessThan(10_000)
  expect(activation.text).toContain('需关联对应站点方可生效')

  const repair = await sendAndRead(page, '用户端故障报修入口在哪里？')
  expect(repair.elapsedMs).toBeLessThan(10_000)
  expect(repair.text).toContain('/charge/pages/malfunction/malfunction')
  expect(repair.text).toContain('项目先完成页面装修配置')
  expect(repair.text).not.toContain('IOT > 故障报修')
})


test('Bug进度查询后同一会话的FAQ不受B路由状态污染', async ({ page }) => {
  const progress = await sendAndRead(
    page,
    '设备白名单执行重置后原有数据丢失，这个问题现在处理到什么进度？',
  )
  expect(progress.text).toContain('设备白名单')
  expect(progress.text).not.toContain('请补充具体')

  const faq = await sendAndRead(page, '计费模板入口在哪里')
  expect(faq.elapsedMs).toBeLessThan(10_000)
  expect(faq.text).toContain('充电桩 > 计费管理 > 充电计费模板')
  expect(faq.text).not.toContain('IOT')
})
