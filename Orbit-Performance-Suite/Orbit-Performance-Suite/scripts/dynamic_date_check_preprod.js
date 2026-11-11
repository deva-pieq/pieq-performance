module.exports = async function (context, commands) {
  const email = "kesav.r+am@pieq.ai";
  const password = "Ab@12345";
  const log = context.log;

  const date = new Date();
  date.setDate(date.getDate() - 1); // one days before today

  // Local date formatted as YYYY-MM-DD
  const formattedDate = [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0")
  ].join("-");

  async function fillInput(id, value) {
    await commands.wait.byId(id, 20000);
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
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype,
            "value"
          ).set;

          setter.call(el, ${JSON.stringify(value)});
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));

          return el.value;
        })();
      `);
    }

    if (actual !== value) {
      throw new Error(
        `Failed to fill #${id}. Expected "${value}", got "${actual}"`
      );
    }

    log.info(`Filled #${id}`);
  }

  // Login setup (not measured)
  await commands.navigate("https://preprod.orbit.pieq.ai/");

  await commands.wait.byId("username", 20000);
  await commands.wait.byId("password", 20000);
  await fillInput("username", email);
  await fillInput("password", password);

  await commands.wait.byTime(500);
  await commands.click.byIdAndWait("kc-login");

  const pages = [
    {
      name: "JFK Operational Command",
      url: `https://preprod.orbit.pieq.ai/airport-monitor/airport/JFK?date=${formattedDate}`
    },
    {
      name: "JFK Live Arrivals Monitor",
      url: `https://preprod.orbit.pieq.ai/airport-monitor/live-arrivals/JFK?date=${formattedDate}`
    },
    {
      name: "POE Master",
      url: "https://preprod.orbit.pieq.ai/poe-master"
    }
  ];

  for (const page of pages) {
    await commands.measure.start(page.name);
    await commands.navigate(page.url);
    await commands.wait.byTime(5000);
    await commands.measure.stop();
  }
};