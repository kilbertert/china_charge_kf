import { expect, test } from '@playwright/test'

async function answerEveryQuestion(page: import('@playwright/test').Page) {
  const cards = page.locator('.hc-question-card')
  const count = await cards.count()
  expect(count).toBeGreaterThan(0)
  for (let index = 0; index < count; index += 1) {
    await cards.nth(index).locator('button').first().click()
  }
}

test('骨密度报告经过固定量表后进入建议页', async ({ page }) => {
  await page.goto('./?view=health')
  await page.locator('textarea.hc-input').fill('腰椎 L1-L4 T值 -2.1')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.getByText('分析报告')).toBeVisible()

  await page.getByRole('button', { name: '开始分析原因' }).click()
  await expect(page.getByText('骨量减少原因筛查表')).toBeVisible()
  await answerEveryQuestion(page)
  await page.getByRole('button', { name: '开始分析原因' }).click()

  await expect(page.getByText('健康建议')).toBeVisible()
  await expect(page.getByText('建议就诊:')).toBeVisible()
})

test('非紧急腿痛量表完成后进入建议页', async ({ page }) => {
  await page.goto('./?view=health')
  await page.locator('textarea.hc-input').fill('我腿疼')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.getByText('腿疼症状甄别表')).toBeVisible()

  await answerEveryQuestion(page)
  await page.getByRole('button', { name: '开始分析原因' }).click()

  await expect(page.getByText('健康建议')).toBeVisible()
  await expect(page.getByText('建议就诊:')).toBeVisible()
})
