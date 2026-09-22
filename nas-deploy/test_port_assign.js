/* 单元测试：__arcadePorts 端口分配纯函数
 * 从已打补丁的 Player-BwKb4RpM.js 里原样抽出台面依赖（Je/pt/ht + __arcadePorts），
 * 断言：端口分配正确、键盘只落一个端口、未用端口绝不出现 -1（RetroArch 会 wasm panic）。
 * 运行：node test_port_assign.js
 */
const fs = require("fs");
const path = require("path");

const FILE = path.join(__dirname, "Player-BwKb4RpM.js");
const src = fs.readFileSync(FILE, "utf8");

function slice(from, to) {
  const a = src.indexOf(from);
  if (a < 0) throw new Error("找不到起点: " + from);
  const b = src.indexOf(to, a);
  if (b < 0) throw new Error("找不到终点: " + to);
  return src.slice(a, b + to.length);
}

// Je=[ ... ]
const jeSrc = slice("Je=[", "]");
// pt={ ... },Kt=   —— slice 含终点；去掉尾部 ",Kt={" 后 pt 的 "}" 已在其中
const ptSrc = slice("pt={", ",Kt={").replace(/,Kt=\{$/, "");
// ht={ ... };function __arcadePorts
const htSrc = slice("ht={", "};function __arcadePorts").replace(/};function __arcadePorts$/, "};");
// function __arcadePorts(...){ ... return{...}}
const fnSrc = slice("function __arcadePorts", "return{cfg:cfg,kbPort:kbPort,padPorts:pads}}");
// function __arcadePadBridgeOff(...){ ... return p!==kbPort}
const brSrc = slice("function __arcadePadBridgeOff", "return p!==kbPort}");

const factory = new Function(
  "const " + jeSrc + ";\nconst " + ptSrc + ";\nconst " + htSrc + "\n" + fnSrc + "\n" + brSrc +
    "\nreturn {__arcadePorts:__arcadePorts,__arcadePadBridgeOff:__arcadePadBridgeOff};"
);
const mod = factory();
const __arcadePorts = mod.__arcadePorts;
const __arcadePadBridgeOff = mod.__arcadePadBridgeOff;

// 从产物里取台面常量，供断言用（避免硬编码漂移）
const PT = new Function("const " + ptSrc + ";return pt;")();
const HT = new Function("const " + htSrc + ";return ht;")();
const KEYS = new Function("const " + jeSrc + ";return Je.map(x=>x.key);")();

let pass = 0,
  fail = 0;
function ok(cond, msg) {
  if (cond) {
    pass++;
  } else {
    fail++;
    console.log("  ✗ " + msg);
  }
}
function eq(a, b, msg) {
  ok(a === b, msg + " (期望 " + JSON.stringify(b) + "，实际 " + JSON.stringify(a) + ")");
}

function assertNoNegOne(r, name) {
  for (const k in r.cfg) if (r.cfg[k] === -1) ok(false, name + ": " + k + " === -1");
  for (let p = 1; p <= 4; p++) {
    ok(!(r.cfg["input_player" + p + "_joypad_index"] === -1), name + ": player" + p + " joypad_index === -1");
  }
}
function kbOf(r, port) {
  // 键盘端口：主键位应等于用户映射
  return r.cfg["input_player" + port + "_up"];
}

console.log("== 1) 旧行为：无 portOrder，1 手柄 + 键盘 1P ==");
{
  const r = __arcadePorts({ kbPlayer: 1 }, [0]);
  eq(r.kbPort, 1, "kbPort=1");
  eq(r.padPorts[0], 1, "手柄 slot0 -> 1P");
  eq(kbOf(r, 1), PT.up, "1P 键盘 up 生效");
  eq(r.cfg["input_player1_joypad_index"], 0, "1P joypad_index=0");
  eq(r.cfg["input_player2_joypad_index"], 1, "2P 空位指向空闲 slot 1");
  eq(r.cfg["input_player2_up"], "nul", "2P 键盘被置 nul");
  eq(r.cfg["input_player1_a_btn"], HT.a, "1P a 按钮 = 手柄 0");
  assertNoNegOne(r, "case1");
}

console.log("== 2) 旧行为：无 portOrder，2 手柄 + 键盘 2P ==");
{
  const r = __arcadePorts({ kbPlayer: 2 }, [0, 2]);
  eq(r.kbPort, 2, "kbPort=2");
  eq(r.padPorts[0], 1, "slot0 -> 1P");
  eq(r.padPorts[2], 2, "slot2 -> 2P");
  eq(kbOf(r, 2), PT.up, "2P 键盘 up 生效");
  eq(r.cfg["input_player1_up"], "nul", "1P 键盘 nul（键盘已给 2P）");
  eq(r.cfg["input_player1_joypad_index"], 0, "1P joypad_index=0");
  eq(r.cfg["input_player2_joypad_index"], 2, "2P joypad_index=2");
  eq(r.cfg["input_player3_joypad_index"], 1, "3P 空位 = 空闲 slot 1");
  eq(r.cfg["input_player4_joypad_index"], 3, "4P 空位 = 空闲 slot 3");
  assertNoNegOne(r, "case2");
}

console.log("== 3) portOrder=[pad,kb,pad,pad] + 2 手柄 ==");
{
  const r = __arcadePorts({ portOrder: ["pad", "kb", "pad", "pad"] }, [1, 3]);
  eq(r.kbPort, 2, "键盘落 2P");
  eq(r.padPorts[1], 1, "第 1 只手柄 -> 1P");
  eq(r.padPorts[3], 3, "第 2 只手柄 -> 3P");
  eq(kbOf(r, 2), PT.up, "2P 键盘生效");
  eq(r.cfg["input_player1_up"], "nul", "1P 键盘 nul");
  eq(r.cfg["input_player3_up"], "nul", "3P 键盘 nul");
  eq(r.cfg["input_player1_joypad_index"], 1, "1P joypad_index=1");
  eq(r.cfg["input_player3_joypad_index"], 3, "3P joypad_index=3");
  ok(r.cfg["input_player2_joypad_index"] !== -1, "2P 空位非 -1");
  ok(r.cfg["input_player4_joypad_index"] !== -1, "4P 空位非 -1");
  assertNoNegOne(r, "case3");
}

console.log("== 4) portOrder=[kb,pad,...] + 1 手柄 ==");
{
  const r = __arcadePorts({ portOrder: ["kb", "pad", "pad", "pad"] }, [0]);
  eq(r.kbPort, 1, "键盘落 1P");
  eq(r.padPorts[0], 2, "手柄 -> 2P");
  eq(kbOf(r, 1), PT.up, "1P 键盘生效");
  eq(r.cfg["input_player2_joypad_index"], 0, "2P joypad_index=0");
  eq(r.cfg["input_player2_a_btn"], HT.a, "2P a 按钮 = 手柄 0");
  assertNoNegOne(r, "case4");
}

console.log("== 5) 极端：0 设备 / 4 手柄 / 键盘自定义映射 ==");
{
  const r0 = __arcadePorts({}, []);
  ok(r0.kbPort >= 1, "无设备时仍有键盘端口");
  assertNoNegOne(r0, "case5-none");

  const r4 = __arcadePorts({ kbPlayer: 4 }, [0, 1, 2, 3]);
  eq(r4.kbPort, 4, "4 手柄时键盘 4P");
  eq(r4.cfg["input_player4_up"], PT.up, "4P 键盘生效");
  assertNoNegOne(r4, "case5-four");

  const rk = __arcadePorts({ kbPlayer: 1, keyboard: { up: "i", start: "1" } }, [0]);
  eq(rk.cfg["input_player1_up"], "i", "自定义键盘 up 生效");
  eq(rk.cfg["input_player1_start"], "1", "自定义键盘 start 生效");
  assertNoNegOne(rk, "case5-custom");
}

console.log("== 6) 所有端口都写出完整键位（14 键）==");
{
  const r = __arcadePorts({ portOrder: ["pad", "kb", "pad", "pad"] }, [2]);
  for (let p = 1; p <= 4; p++) {
    for (const k of KEYS) {
      ok(
        Object.prototype.hasOwnProperty.call(r.cfg, "input_player" + p + "_" + k),
        "缺 input_player" + p + "_" + k
      );
    }
    ok(
      Object.prototype.hasOwnProperty.call(r.cfg, "input_player" + p + "_joypad_index"),
      "缺 player" + p + " joypad_index"
    );
  }
  // 手柄端口必须有 _btn
  ok(r.cfg["input_player1_a_btn"] === HT.a, "手柄端口写 _btn");
}

console.log("== 7) 桥闸门 __arcadePadBridgeOff：手柄与键盘不同端口时必须关桥 ==");
{
  // 用户实测的 bug 场景：portOrder=[pad,kb,pad,pad] + 1 手柄 → 手柄端口1、键盘端口2
  const r = __arcadePorts({ portOrder: ["pad", "kb", "pad", "pad"] }, [0]);
  ok(
    __arcadePadBridgeOff(0, r.padPorts, r.kbPort, true) === true,
    "手柄(1P)与键盘(2P)不同端口 → 必须关桥（否则一次投币记 2 个币）"
  );
  // 旧行为 kbPlayer=1 + 1 手柄：手柄与键盘同在 1P → 保留桥（不改变既有行为）
  const r1 = __arcadePorts({ kbPlayer: 1 }, [0]);
  ok(
    __arcadePadBridgeOff(0, r1.padPorts, r1.kbPort, true) === false,
    "手柄与键盘同在 1P → 保留桥（零回归）"
  );
  // 键盘 1P + 手柄 2P：手柄端口2、键盘端口1 → 关桥
  const r2 = __arcadePorts({ portOrder: ["kb", "pad", "pad", "pad"] }, [3]);
  eq(r2.padPorts[3], 2, "手柄落 2P");
  ok(
    __arcadePadBridgeOff(3, r2.padPorts, r2.kbPort, true) === true,
    "键盘1P/手柄2P → 关桥"
  );
  // 用户显式关掉开关 → 永不关桥（保留旧行为，可一键回退）
  ok(
    __arcadePadBridgeOff(0, r.padPorts, r.kbPort, false) === false,
    "nativeOnly=false → 永不关桥"
  );
  // 手柄没有原生端口（没分配）→ 保留桥，避免彻底没输入
  ok(__arcadePadBridgeOff(0, null, 1, true) === false, "无 padPorts → 保留桥");
  ok(__arcadePadBridgeOff(7, r.padPorts, r.kbPort, true) === false, "无原生端口的槽位 → 保留桥");
  // 2 手柄、键盘 2P 时：手柄1(端口1) 关桥、手柄2(端口3) 也关桥
  const r3 = __arcadePorts({ portOrder: ["pad", "kb", "pad", "pad"] }, [0, 2]);
  ok(__arcadePadBridgeOff(0, r3.padPorts, r3.kbPort, true) === true, "2 手柄：slot0 关桥");
  ok(__arcadePadBridgeOff(2, r3.padPorts, r3.kbPort, true) === true, "2 手柄：slot2 关桥");
}

console.log("\n" + (fail === 0 ? "PASS" : "FAIL") + "  " + pass + " passed, " + fail + " failed");
process.exit(fail === 0 ? 0 : 1);
