// 从产物里切出 __arcadeSeat* / __arcadeSlots 喂各种状态（无头之外的第一道闸门）。
// 规则（2026-09-14 用户拍板）：**只有按 START 才入座**，投币键只是投币、不占位。
// 用法: node test_input_router.js
const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, 'Player-BwKb4RpM.js')
const text = fs.readFileSync(SRC, 'utf8')

function grab(name) {
  const i = text.indexOf('function ' + name + '(')
  if (i < 0) throw new Error('找不到 ' + name)
  // 这几个函数体里没有嵌套的大括号函数，直接配平即可
  let d = 0, started = false
  for (let j = i; j < text.length; j++) {
    if (text[j] === '{') { d++; started = true }
    else if (text[j] === '}') { d--; if (started && d === 0) return text.slice(i, j + 1) }
  }
  throw new Error(name + ' 配平失败')
}

const NAMES = ['__arcadeSeatClaim', '__arcadeSeatRelease', '__arcadeSeatPlan', '__arcadeSeatSlot', '__arcadeSlots']
const code = NAMES.map(grab).join('\n')

// 切出来的必须是「线上真正在跑的那段」——含本次新规则特征子串，否则测试是假绿
if (!/if\(btn!=='start'\)return claim;/.test(code)) {
  throw new Error('切到的 __arcadeSeatClaim 不是「只有 START 入座」版本，测试无效')
}
if (/btn!=='select'/.test(code)) {
  throw new Error('切到的代码里投币键还能认领 —— 说明切到了旧版本')
}

// __arcadeSlots 依赖产物里的 Je（按钮清单）与 ht（标准 XInput 索引）
const Je = [{ key: 'up' }, { key: 'down' }, { key: 'left' }, { key: 'right' }, { key: 'a' }, { key: 'b' },
  { key: 'x' }, { key: 'y' }, { key: 'l' }, { key: 'r' }, { key: 'l2' }, { key: 'r2' },
  { key: 'start' }, { key: 'select' }]
const ht = { a: 1, b: 0, x: 3, y: 2, l: 4, r: 5, l2: 6, r2: 7, select: 8, start: 9, up: 12, down: 13, left: 14, right: 15 }

const factory = new Function('Je', 'ht', code + '\nreturn {' + NAMES.join(',') + '}')
const R = factory(Je, ht)

let pass = 0, fail = 0
function eq(actual, expected, msg) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected)
  if (a === e) { pass++; return }
  fail++
  console.log('  ✗ ' + msg + '\n      期望 ' + e + '\n      实际 ' + a)
}
const E = [null, null, null, null]

// ---- 1. 认领规则：只有按 START 才算加入，投币键不占位 ----
eq(R.__arcadeSeatClaim(E, 'kb', 'a'), E, '按普通键(a) 不认领')
eq(R.__arcadeSeatClaim(E, 'kb', 'up'), E, '按方向键 不认领')
eq(R.__arcadeSeatClaim(E, 'kb', 'select'), E, '按投币键 不认领（只有 START 才入座）')
eq(R.__arcadeSeatClaim(E, 'kb', 'start'), ['kb', null, null, null], '按 START → 键盘占 1P')
eq(R.__arcadeSeatClaim(['kb', null, null, null], 'kb', 'start'), ['kb', null, null, null], '已占位的设备不会再占第二个位')
eq(R.__arcadeSeatClaim(['kb', null, null, null], 'pad:0', 'select'), ['kb', null, null, null], '手柄按投币 不认领')
eq(R.__arcadeSeatClaim(['kb', null, null, null], 'pad:0', 'start'), ['kb', 'pad:0', null, null], '手柄按 START → 占 2P')
eq(R.__arcadeSeatClaim(['kb', 'pad:0', null, null], 'peera', 'start'), ['kb', 'pad:0', 'peera', null], '远端按 START → 占 3P')

// ---- 2. 顺序 = 按 START 的先后（谁先按谁先占） ----
let c = E
c = R.__arcadeSeatClaim(c, 'pad:1', 'start')
eq(c, ['pad:1', null, null, null], '手柄先按 START → 手柄当 1P（不区分键盘手柄）')
c = R.__arcadeSeatClaim(c, 'kb', 'start')
eq(c, ['pad:1', 'kb', null, null], '键盘后按 START → 2P')
c = R.__arcadeSeatClaim(c, 'pad:0', 'start')
eq(c, ['pad:1', 'kb', 'pad:0', null], '第三只设备 → 3P')
c = R.__arcadeSeatClaim(c, 'peerB', 'start')
eq(c, ['pad:1', 'kb', 'pad:0', 'peerB'], '第四个 → 4P')
eq(R.__arcadeSeatClaim(c, 'pad:2', 'start'), c, '第 5 个设备按 START 也入不了座（旁观）')
eq(R.__arcadeSeatClaim(c, 'pad:2', 'select'), c, '第 5 个设备按投币也不认领')

// ---- 3. 释放与补位 ----
eq(R.__arcadeSeatRelease(['kb', 'pad:0', null, 'p1'], 'pad:0'), ['kb', null, null, 'p1'], '释放中间席位 → 留洞')
eq(R.__arcadeSeatRelease(['kb', 'pad:0', null, null], 'pad:9'), ['kb', 'pad:0', null, null], '释放不存在的设备 = 无变化')
eq(R.__arcadeSeatClaim(['kb', null, null, 'p1'], 'pad:0', 'start'), ['kb', 'pad:0', null, 'p1'], '新设备补到最小空位（不是补到 4P）')
eq(R.__arcadeSeatClaim(R.__arcadeSeatRelease(['kb', 'pad:0', null, null], 'pad:0'), 'pad:0', 'start'),
  ['kb', 'pad:0', null, null], '释放后同一设备再按 START 能重入')

// ---- 4. 席位投影：还没按 START 时也能操作；满座后就是旁观 ----
eq(R.__arcadeSeatPlan(E, ['kb']), { 0: 'kb' }, '没人入座时键盘投影到 1P（所以按 START 前也能操作）')
eq(R.__arcadeSeatPlan(E, ['kb', 'pad:0']), { 0: 'kb', 1: 'pad:0' }, '两个未入座设备各投影一个空位')
eq(R.__arcadeSeatPlan(['pad:1', null, null, null], ['kb', 'pad:1']), { 0: 'pad:1', 1: 'kb' }, '已入座在原位，未入座投影到空位')
eq(R.__arcadeSeatPlan(['a', 'b', 'c', 'd'], ['kb']), { 0: 'a', 1: 'b', 2: 'c', 3: 'd' }, '满座后未入座设备投影不到任何位')
eq(R.__arcadeSeatSlot(['a', 'b', 'c', 'd'], 'kb'), -1, '满座 + 未入座 → -1（不驱动任何玩家）')
eq(R.__arcadeSeatSlot(['kb', null, null, null], 'kb'), 0, '已入座返回自己的席位')
eq(R.__arcadeSeatSlot(E, 'kb'), 0, '未入座返回投影位')

// ---- 5. 配置产物 ----
const RP = R.__arcadeSlots()
eq(RP.cfg.input_player1_joypad_index, 0, '1P 槽位 → 手柄槽 0')
eq(RP.cfg.input_player4_joypad_index, 3, '4P 槽位 → 手柄槽 3')
eq(RP.cfg.input_player1_a_btn, 1, '1P A 键 = 标准 XInput 1')
eq(RP.cfg.input_player1_select_btn, 8, '1P 投币 = 标准 XInput 8')
eq(RP.cfg.input_player1_start_btn, 9, '1P START = 标准 XInput 9')
eq(RP.cfg.input_player1_up, 'nul', '1P 键盘方向键已被关掉（走路由器的虚拟手柄）')
eq(RP.cfg.input_player3_select, 'nul', '3P 键盘投币也是 nul')
eq(RP.kbPort, 0, '不再有键盘专属端口')

console.log('\n' + (fail ? '失败 ' + fail + ' 条 / ' : '') + '通过 ' + pass + ' 条断言')
process.exit(fail ? 1 : 0)
