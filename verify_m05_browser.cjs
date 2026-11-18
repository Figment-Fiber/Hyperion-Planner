const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const url = process.env.HYPERION_URL || "http://127.0.0.1:8781";
const output = process.env.HYPERION_M05_OUTPUT || path.join(__dirname, "evidence", "m05", "browser");
fs.mkdirSync(output, {recursive:true});

function fixture() {
  return {
    version:2,project_id:"m05-browser-fixture",revision:1,route_name:"Oahu Engineering Review",
    network:{
      nodes:[{id:"A",name:"Kapolei",lat:21.335,lon:-158.058},{id:"B",name:"Honolulu",lat:21.307,lon:-157.858},
        {id:"C",name:"Central ROADM",lat:21.39,lon:-157.96},{id:"D",name:"Branch terminal",lat:21.46,lon:-157.95}],
      links:[
        {id:"ac",from:"A",to:"C",bends:[[21.36,-158.04]],override:null,splices:[.1],inline_gain:null,fiber:{type_variety:"SSMF",loss_coef:.2}},
        {id:"cb",from:"C",to:"B",bends:[],override:23,splices:[],inline_gain:null,fiber:{type_variety:"SSMF",loss_coef:.2}},
        {id:"cd",from:"C",to:"D",bends:[],override:null,splices:[],inline_gain:null,fiber:{type_variety:"SSMF",loss_coef:.2}},
      ],
      services:[{id:"service-1",source:"A",target:"B",via:[]}]},
    active_service:"service-1",equipment:{vendor:"generic",service_gbps:100,mode:"advanced",nodes:{}},
    tx_power_dbm:null,booster_gain_db:null,preamp_gain_db:null,
    quality_limits:{threshold:45,reserve:2,warning:1},ase_threshold_db:45,ase_warning_db:1,
  };
}

async function main() {
  const browser = await chromium.launch({executablePath:process.env.HYPERION_BROWSER || undefined});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
    const errors=[];
    page.on("pageerror", error=>errors.push(error.message));
    await page.goto(url);
    await page.locator("#auto-run").uncheck();
    await page.waitForFunction(()=>!/Checking|Ready to design|Running GNPy/.test(document.getElementById("status").textContent),{timeout:30000});
    assert.deepEqual(errors,[]);
    assert.equal(await page.locator(".brand span").innerText(),"Hyperion");
    for(const [caseName,length] of [["bundled",80],["override",85.25]]) {
      if(caseName==="bundled")await page.locator("#reference").click();
      else {
        await page.locator("#network-list").getByRole("button",{name:"Kapolei → Honolulu",exact:true}).click();
        await page.locator("#span-length").fill(String(length));
        await page.locator("#span-length").blur();
      }
      await page.waitForTimeout(650);
      const response=page.waitForResponse(response=>response.url().endsWith("/api/run"),{timeout:100000});
      await page.locator("#run").click();
      const actual=await (await response).json();
      assert.equal(actual.span_length_km,length);
      const raw=fs.readFileSync(path.join(__dirname,"evidence","gnpy-3.0.1",caseName+".stdout.txt"),"utf8");
      const expected=raw.split("Channel frequency (THz)")[1].split(/\r?\n/).map(line=>line.trim().split(/\s+/)).filter(row=>row.length===6&&/^\d+$/.test(row[0])).map(row=>row.map(Number));
      assert.equal(expected.length,76);
      assert.deepEqual(actual.channels.map(row=>[row.channel,row.frequency_thz,row.power_dbm,row.osnr_ase_db,row.snr_nli_db,row.gsnr_db]),expected);
      fs.writeFileSync(path.join(output,caseName+".json"),JSON.stringify(actual,null,2));
    }
    assert.match(await page.locator("#span-readings").innerText(),/Over 80 km/);
    await page.locator("#suggest-amplifier").click();
    await page.waitForTimeout(700);
    assert.doesNotMatch(await page.locator("#span-readings").innerText(),/Over 80 km/);
    assert(Number(await page.locator("#inline-gain").inputValue())>=8);
    const load = async design => {
      const response=page.waitForResponse(response=>response.url().endsWith("/api/preview"));
      await page.locator("#route-file").setInputFiles({name:"fixture.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(design))});
      assert.equal((await response).status(),200);
      await page.waitForFunction(name=>document.getElementById("route-name").value===name,design.route_name);
      await page.waitForTimeout(500);
    };
    await load(fixture());
    assert.equal(await page.locator("#network-list button").count(),7);
    await page.locator("#network-list").getByRole("button",{name:"C · Central ROADM · 3°",exact:true}).click();
    await page.locator("#panel-connector-loss").fill("0.8");
    await page.locator("#panel-connector-loss").blur();
    await page.locator("#roadm-path-loss").fill("2");
    await page.locator("#roadm-path-loss").blur();
    await page.waitForTimeout(600);
    await page.locator("#network-list").getByRole("button",{name:"A · Kapolei · 1°",exact:true}).click();
    await page.locator("#service-rate").selectOption("400");
    await page.locator("#vendor").selectOption("ciena");
    await page.waitForTimeout(700);
    const incompatible=page.locator(".equipment-option.incompatible").first();
    await incompatible.focus();
    await page.keyboard.press("Enter");
    assert(await page.locator("#option-detail").isVisible());
    assert.match(await page.locator("#option-reason").innerText(),/400|preset|Ciena/);
    await page.getByRole("button",{name:"Close",exact:true}).click();
    await page.locator("#service-rate").selectOption("100");
    await page.locator("#vendor").selectOption("generic");
    await page.locator("#network-list").getByRole("button",{name:"Kapolei → Central ROADM",exact:true}).click();
    await page.waitForTimeout(700);
    const original=await page.locator("#span-readings").innerText();
    await page.locator("#draw-bend").click();
    const box=await page.locator("#map").boundingBox();
    await page.locator("#map").click({position:{x:box.width*.42,y:box.height*.3}});
    await page.waitForTimeout(700);
    assert.notEqual(await page.locator("#span-readings").innerText(),original);
    await page.locator("#undo").click();
    await page.locator("#network-list").getByRole("button",{name:"Kapolei → Central ROADM",exact:true}).click();
    await page.waitForTimeout(700);
    assert.equal(await page.locator("#span-readings").innerText(),original);
    await page.locator("#redo").click();
    await page.waitForTimeout(600);
    await page.locator("#network-list").getByRole("button",{name:"Kapolei → Central ROADM",exact:true}).click();
    await page.locator("#span-length").fill("30");
    await page.locator("#span-length").blur();
    await page.getByRole("button",{name:"Add splice",exact:true}).click();
    await page.locator("#fiber-type").selectOption("LOF");
    await page.locator("#fiber-loss").fill("0.17");
    await page.locator("#fiber-loss").blur();
    const widthBefore=(await page.locator("#route-settings").boundingBox()).width;
    await page.locator("#settings-resize").focus();
    await page.keyboard.press("ArrowLeft");
    assert((await page.locator("#route-settings").boundingBox()).width>widthBefore);
    const heightBefore=(await page.locator("#map").boundingBox()).height;
    await page.locator("#map-resize").focus();
    await page.keyboard.press("ArrowDown");
    assert((await page.locator("#map").boundingBox()).height>heightBefore);
    const response=page.waitForResponse(response=>response.url().endsWith("/api/run"),{timeout:100000});
    await page.locator("#run").click();
    const result=await (await response).json();
    assert.equal(result.channels.length,76);
    assert.equal(result.spans[0].simulation_km,30);
    assert.equal(result.spans[0].splice_total_db,.2);
    assert.equal(result.selected_path.degrees.C,3);
    assert.match(result.report,/Roadm_C/);
    assert.equal(await page.locator("#channels tr").count(),76);
    assert.match(await page.locator("#results-checks").innerText(),/Fail/);
    const download=page.waitForEvent("download");
    await page.locator("#download").click();
    await (await download).saveAs(path.join(output,"completed-run.xlsx"));
    const save=page.waitForEvent("download");
    await page.locator("#save-route").click();
    const saved=await save;
    await saved.saveAs(path.join(output,"saved-project.json"));
    const content=JSON.parse(fs.readFileSync(path.join(output,"saved-project.json"),"utf8"));
    assert.equal(content.network.nodes.length,4);
    assert.equal(content.equipment_summary.scope,"Full saved physical network");
    assert.equal(content.network.links[0].bends.length,2);
    await page.locator("#new-route").click();
    await load(content);
    assert.equal(await page.locator("#network-list button").count(),7);
    await page.screenshot({path:path.join(output,"desktop.png"),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.locator("#run").isVisible());
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(output,"mobile.png"),fullPage:true});
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,"run.json"),JSON.stringify(result,null,2));
    console.log("M05 browser passed: branched route, panels, WSS inputs, incompatibility explanation, bends, undo/redo, fiber, losses, resizing, 76 channel rows, project/Excel download and mobile.");
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
