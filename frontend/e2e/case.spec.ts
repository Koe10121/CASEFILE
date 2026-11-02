import { expect, test, type Page } from "@playwright/test";

// CASE #001 played start to finish in a real browser, with the mock AI. It follows the
// same winning route as the backend's test_the_case_is_winnable_over_http, but through
// the buttons a player uses, so it also catches a broken page, route or proxy.

async function talk(page: Page, name: string): Promise<void> {
  await page
    .getByRole("navigation", { name: "Investigation" })
    .getByRole("button", { name })
    .click();
  await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
}

async function search(page: Page, place: string): Promise<void> {
  const button = page
    .getByRole("navigation", { name: "Investigation" })
    .getByRole("button", { name: place });
  await button.click();
  await expect(button).toContainText("searched");
}

async function show(page: Page, evidence: string): Promise<void> {
  await page.getByLabel("Evidence to show").selectOption(evidence);
  const done = page.waitForResponse((r) => r.url().endsWith("/show"));
  await page.getByRole("button", { name: "Show", exact: true }).click();
  expect((await done).status()).toBe(200);
}

test("a detective can solve CASE #001 in the browser", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") problems.push(m.text());
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "The Last Evening at Blackwood Manor",
  );
  await page.getByText("Normal", { exact: true }).click();
  await page.getByRole("button", { name: "Take the case" }).click();
  await expect(page).toHaveURL(/\/game\/[\w-]+$/);

  // Thomas opens with his statement, then answers a question.
  await talk(page, "Thomas Reid");
  await page.getByLabel("Your question").fill("Did you hear Arthur's voice through the intercom?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("Did you hear Arthur's voice through the intercom?")).toBeVisible();
  await expect(page.getByText("Thomas Reid is thinking…")).toBeHidden();

  await search(page, "Study");
  await search(page, "Hall");

  // A reload resumes the same game from the server.
  await page.reload();
  await expect(page.getByRole("heading", { level: 2, name: "Thomas Reid" })).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Investigation" }).getByRole("button", { name: "Study" }),
  ).toContainText("searched");

  // Victoria's lies break one by one when she is shown the right evidence.
  await talk(page, "Victoria Shaw");
  await show(page, "E05");
  await expect(page.getByText("You show Study wall panel.")).toBeVisible();
  await show(page, "E04");
  await show(page, "E10");
  await search(page, "Guest room 2 (Victoria's)");
  await show(page, "E11");
  await page.getByRole("tab", { name: /Statements/ }).click();
  await expect(page.getByRole("tabpanel").getByText("Disproved")).toHaveCount(3);

  // One hint on Normal, and the counter goes down.
  await page.getByRole("button", { name: "I'm stuck: give me a hint" }).click();
  await expect(page.getByText("2 left", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Make your accusation" }).click();
  await page.getByRole("radio", { name: "Victoria Shaw" }).check();
  await page.locator('input[name="motive"][value="MOT_HIDE_THEFT"]').check();
  await page.locator('input[name="method"][value="MTH_AWARD_STAGED"]').check();
  for (const id of ["E05", "E10", "E02", "E03"]) {
    await page.locator(`input[type="checkbox"][value="${id}"]`).check();
  }
  await page.getByLabel("I'm sure. Close the case.").check();
  await page.getByRole("button", { name: "Accuse", exact: true }).click();

  await expect(page.getByText("Case closed")).toBeVisible();
  await expect(page.getByText("You named the killer.")).toBeVisible();
  await expect(page.locator("p.text-6xl")).toHaveText("100/100");
  await expect(page.getByRole("heading", { name: "What really happened" })).toBeVisible();

  expect(problems).toEqual([]);
});
