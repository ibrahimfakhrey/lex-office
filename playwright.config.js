// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
    testDir: './tests/e2e',
    timeout: 15000,
    expect: { timeout: 10000 },
    retries: 1,
    workers: 1, // Run serially since tests share DB state
    reporter: [['html', { outputFolder: 'tests/playwright-report', open: 'never' }], ['line']],
    use: {
        baseURL: 'http://127.0.0.1:5000',
        headless: false,
        channel: 'chrome',
        screenshot: 'on',
        video: 'retain-on-failure',
        locale: 'ar-EG',
    },
    projects: [
        {
            name: 'chrome',
            use: { ...devices['Desktop Chrome'], channel: 'chrome' },
        },
    ],
});
