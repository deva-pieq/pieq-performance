module.exports = async function (context, commands) {
    const isPreprod = process.env.PERF_ENV === "preprod";
    const baseUrl = isPreprod ? "https://preprod.tandem.pieq.ai" : "https://tandem.pieq.ai";
    const email = "kesav.r@pieq.ai";
    const password = "Ab@12345";
    const workspaceName = "Andrew's Cafe";
    const log = context.log;

    async function fillInput(id, value) {
        await commands.wait.byId(id, 60000);
        await commands.click.byId(id);
        await commands.wait.byTime(300);
        await commands.addText.byId(value, id);

        let actual = await commands.js.run(
            `return document.getElementById(${JSON.stringify(id)})?.value || "";`
        );

        if (actual !== value) {
            log.info(`Selenium fill missed for #${id}, using JS fallback`);
            actual = await commands.js.run(`
                return (function () {
                    const el = document.getElementById(${JSON.stringify(id)});
                    if (!el) throw new Error("Element not found: ${id}");
                    el.focus();
                    const proto = window.HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
                    setter.call(el, ${JSON.stringify(value)});
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                    return el.value;
                })();
            `);
        }

        if (actual !== value) {
            throw new Error(`Failed to fill #${id}. Expected "${value}", got "${actual}"`);
        }
        log.info(`Filled #${id}`);
    }

    async function waitForWorkspaceContext() {
        for (let i = 0; i < 60; i++) {
            const ids = await commands.js.run(`
                return (function () {
                    const params = new URLSearchParams(window.location.search);
                    return {
                        href: window.location.href,
                        workspaceId: params.get("workspaceId") || "",
                        companyId: params.get("companyId") || ""
                    };
                })();
            `);

            if (ids.workspaceId && ids.companyId) {
                log.info(`Workspace context ready: ${ids.href}`);
                return ids;
            }

            log.info(`Waiting for workspace context (${i + 1}/60): ${ids.href}`);
            await commands.wait.byTime(1000);
        }

        throw new Error(`Timed out waiting for ${workspaceName} workspaceId and companyId in the URL`);
    }

    // Tandem is a client-side SPA. Navigating to a route you are already on
    // (or switching only query params) does not trigger a full page load, so
    // browsertime reports "navigation never happened". Reset to about:blank first.
    async function measureUrl(name, url) {
        await commands.navigate("about:blank");
        await commands.measure.start(name);
        await commands.navigate(url);
        await commands.wait.byTime(5000);
        await commands.measure.stop();
    }

    const workspaceTitleXpath = `//h3[contains(normalize-space(.), "${workspaceName}")]`;

    await commands.measure.start("Login");
    await commands.navigate(baseUrl + "/");
    await commands.wait.byId("username", 60000);
    await commands.wait.byId("password", 60000);
    await fillInput("username", email);
    await fillInput("password", password);
    await commands.wait.byTime(500);
    await commands.click.byIdAndWait("kc-login");
    await commands.wait.byXpath(workspaceTitleXpath, 60000);
    await commands.wait.byTime(2000);
    await commands.measure.stop();

    await measureUrl("Restaurant Workspace", `${baseUrl}/workspace`);
    await commands.wait.byXpath(workspaceTitleXpath, 60000);

    log.info(`Restaurant Workspace list loaded, opening ${workspaceName}`);
    await commands.click.byXpath(workspaceTitleXpath);

    const { workspaceId, companyId } = await waitForWorkspaceContext();
    const qs = `workspaceId=${workspaceId}&companyId=${companyId}`;

    const pages = [
        { name: "My Workspace", url: `${baseUrl}/my-workspace?${qs}` },
        { name: "Sync Dashboard", url: `${baseUrl}/sync-dashboard?${qs}` },
        { name: "Monitor and Schedule", url: `${baseUrl}/monitor-schedule?${qs}` },
        { name: "Chats", url: `${baseUrl}/chats?${qs}` },
        { name: "AI Co-workers", url: `${baseUrl}/ai-agents?${qs}` },
        { name: "File Uploads", url: `${baseUrl}/file-uploads?${qs}` },
        { name: "AI Analysis", url: `${baseUrl}/ai-analysis?${qs}` },
        { name: "Settings", url: `${baseUrl}/settings?${qs}` },
        { name: "Integrations", url: `${baseUrl}/account/integrations?${qs}` },
        { name: "Agent Studio", url: `${baseUrl}/agent-studio?${qs}` }
    ];

    for (const page of pages) {
        await measureUrl(page.name, page.url);
    }
};
