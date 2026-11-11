module.exports = async function (context, commands) {
    const isPreprod = process.env.PERF_ENV === "preprod";
    const baseUrl = isPreprod ? "https://preprod.app.pieq.ai" : "https://icm.pieq.ai";
    const email = isPreprod ? "kesav.r@pieq.ai" : "kesav.r@pieq.ai";
    const password = "Ab@12345";
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

    await commands.navigate(baseUrl + "/");
    await commands.wait.byId("username", 60000);

    if (isPreprod) {
        await commands.wait.byId("kc-continue-email", 60000);
        await fillInput("username", email);
        await commands.wait.byTime(500);
        await commands.click.byId("kc-continue-email");
    } else {
        await fillInput("username", email);
        await commands.wait.byTime(500);
        await commands.click.byIdAndWait("kc-login");
    }

    await commands.wait.byId("password", 60000);
    await fillInput("password", password);
    await commands.wait.byTime(500);

    if (isPreprod) {
        await commands.wait.byId("kc-login", 60000);
    }
    await commands.click.byIdAndWait("kc-login");

    const pages = [
        { name: "Dashboard",                  url: baseUrl + "/dashboard/ops-manager" },
        { name: "Policy",                     url: baseUrl + "/policy" },
        { name: "Statement History",          url: baseUrl + "/commission-processing/statement-history" },
        { name: "Needs Attention",            url: baseUrl + "/commission-processing/needs-attention" },
        { name: "Payable",                    url: baseUrl + "/payment-processing/payable-line-items" },
        { name: "User Management",            url: baseUrl + "/user-management" },
        { name: "Carriers",                   url: baseUrl + "/carriers" },
        { name: "Agents",                     url: baseUrl + "/agents" },
        { name: "Products",                   url: baseUrl + "/product" },
        { name: "Commission Statement Setup", url: baseUrl + "/commissions/statement-setup" },
        { name: "Advance Overview",           url: baseUrl + "/advance/overview" },
        { name: "Advance Setup",              url: baseUrl + "/advance/advance-setup" },
        { name: "Upload Commission Statement",url: baseUrl + "/commission-processing/upload-statement" },
        { name: "Disbursement History",       url: baseUrl + "/payment-processing/disbursement-history" },
        { name: "Miscellaneous Charges",      url: baseUrl + "/payment-processing/miscellaneous-charges" }
    ];

    for (const page of pages) {
        await commands.measure.start(page.name);
        await commands.navigate(page.url);
        await commands.wait.byTime(5000);
        await commands.measure.stop();
    }
};
