/* peer-seat 单测：从「线上真正在跑的产物」里切出纯函数与工具函数，喂假状态断言。
   这样测的是线上那段代码，而不是重新手打的近似版本。
   覆盖：
     A) __arcadeSeatClaim —— 只有 START 认领、投币不认领（本地与远端同一规则）
     B) __arcadeSeatPlan  —— 投影逻辑：没座位前也能投币，座位满了就投影不到（旁观）
     C) __arcadeSeatSlot  —— 设备当前占的位
     D) 远端 peer 设备 id 形态 'peer:<id>' 能被 claim/plan/slot 正常处理
     E) 观战（不在 claim 里、且无空位）→ slot = -1（不驱动任何玩家）
*/
const fs = require('fs')
const path = require('path')

const HERE = __dirname
const SRC = fs.readFileSync(path.join(HERE, 'Player-BwKb4RpM.js'), 'utf8')

function cut(from, to) {
  const i = SRC.indexOf(from)
  if (i < 0) throw new Error('anchor not found: ' + from)
  const j = SRC.indexOf(to, i)
  if (j < 0) throw new Error('end anchor not found: ' + to)
  return SRC.slice(i, j)
}

// —— 切出三个纯函数（从 [patch] seats 注释起，到 [patch] slots 之前的函数体结束）
const seatsSrc = cut('function __arcadeSeatClaim(claim,dev,btn)', 'function __arcadeSlots()')
if (!/__arcadeSeatSlot/.test(seatsSrc)) throw new Error('seatsSrc 不完整（缺少 __arcadeSeatSlot）')
console.log('切出 seats 代码长度:', seatsSrc.length)

const api = new Function(seatsSrc + '; return { __arcadeSeatClaim, __arcadeSeatRelease, __arcadeSeatPlan, __arcadeSeatSlot };')()

let pass = 0, fail = 0
function ok(cond, label, extra) {
  if (cond) { pass++; console.log('PASS  ' + label) }
  else { fail++; console.log('FAIL  ' + label + (extra !== undefined ? '  ' + JSON.stringify(extra) : '')) }
}
function eq(a, b, label) {
  ok(JSON.stringify(a) === JSON.stringify(b), label, { got: a, want: b })
}

const { __arcadeSeatClaim, __arcadeSeatRelease, __arcadeSeatPlan, __arcadeSeatSlot } = api

console.log('\n=== A) __arcadeSeatClaim：只有 START 认领 ===')
eq(__arcadeSeatClaim([], 'kb', 'start'), ['kb', null, null, null], 'START → 占 1P')
eq(__arcadeSeatClaim([], 'kb', 'select'), [null, null, null, null], '投币(select) → 不认领')
eq(__arcadeSeatClaim([], 'kb', 'a'), [null, null, null, null], '普通键 a → 不认领')
eq(__arcadeSeatClaim([], 'kb', undefined), [null, null, null, null], '无 btn → 不认领')
eq(__arcadeSeatClaim([], 'kb', 'down'), [null, null, null, null], '方向键 → 不认领')

console.log('\n=== A2) 依次入座，占满 4 席 ===')
let c = []
for (const d of ['kb', 'pad:0', 'peer:abc12345', 'pad:1']) {
  c = __arcadeSeatClaim(c, d, 'start')
}
eq(c, ['kb', 'pad:0', 'peer:abc12345', 'pad:1'], '4 个设备依次占 1P..4P')

console.log('\n=== A3) 第 5 个设备 START → 抢不到（旁观） ===')
const c5 = __arcadeSeatClaim(c, 'peer:zzzz9999', 'start')
eq(c5, c, '座位已满 → claim 不变（旁观）')

console.log('\n=== A4) 重复 START 不会占两个位 ===')
const cDup = __arcadeSeatClaim(c, 'kb', 'start')
eq(cDup, c, '已在座的设备再按 START → 不变')

console.log('\n=== B) __arcadeSeatPlan：投影（没座位前也能投币） ===')
/* 注意：__arcadeSeatPlan 返回的是「稀疏对象」{槽位下标: 设备id}，不是密集数组。
   这是线上真实契约（build() 那边按 plan[s] 取值，undefined 自然当空槽），别按数组断言。 */
eq(__arcadeSeatPlan([], ['kb', 'pad:0']), { 0: 'kb', 1: 'pad:0' }, '无人认领 → 按顺序投影')
eq(__arcadeSeatPlan(c, ['kb', 'pad:0', 'peer:abc12345', 'pad:1']), { 0: 'kb', 1: 'pad:0', 2: 'peer:abc12345', 3: 'pad:1' }, '全部已认领 → 计划=认领')
const planFull = __arcadeSeatPlan(c, ['kb', 'pad:0', 'peer:abc12345', 'pad:1', 'peer:zzzz9999'])
eq(planFull, { 0: 'kb', 1: 'pad:0', 2: 'peer:abc12345', 3: 'pad:1' },
  '5 个设备抢 4 席 → 第 5 个投影不到（旁观）')
ok(planFull[4] === undefined, '第 5 个设备不在计划里（槽位 4 不存在）')

console.log('\n=== B2) 部分认领 + 新设备投影到空位 ===')
const partClaim = ['kb', null, null, null]
eq(__arcadeSeatPlan(partClaim, ['kb', 'pad:0']), { 0: 'kb', 1: 'pad:0' },
  'kb 占 1P，pad:0 投影到 2P')

console.log('\n=== C) __arcadeSeatSlot ===')
eq(__arcadeSeatSlot(c, 'kb'), 0, 'kb → 0 (1P)')
eq(__arcadeSeatSlot(c, 'pad:0'), 1, 'pad:0 → 1 (2P)')
eq(__arcadeSeatSlot(c, 'peer:abc12345'), 2, 'peer:abc12345 → 2 (3P)')
eq(__arcadeSeatSlot(c, 'peer:zzzz9999'), -1, '满座且未认领 → -1（旁观，驱动不到任何玩家）')
eq(__arcadeSeatSlot(['kb', null, null, null], 'pad:0'), 1, '未认领 + 有空位 → 投影位 1')

console.log('\n=== D) 远端 peer 设备 id 形态 ===')
const peerIds = ['peer:a', 'peer:abcdefgh', 'peer:12345678']
let pc = []
for (const p of peerIds) pc = __arcadeSeatClaim(pc, p, 'start')
eq(pc, ['peer:a', 'peer:abcdefgh', 'peer:12345678', null], '3 个远端 peer 依次占 1P..3P')
eq(__arcadeSeatSlot(pc, 'peer:abcdefgh'), 1, 'peer:abcdefgh → 2P')

console.log('\n=== E) 观战：满座 + 未认领 → slot -1 ===')
eq(__arcadeSeatSlot(c, 'peer:newguy01'), -1, '满座且未认领 → -1（不驱动任何玩家）')
eq(__arcadeSeatSlot(c, 'kb' + 'x'), -1, '未知设备 id → -1')

console.log('\n=== F) __arcadeSeatRelease ===')
eq(__arcadeSeatRelease(c, 'pad:0'), ['kb', null, 'peer:abc12345', 'pad:1'], '释放 pad:0 → 2P 空出')
eq(__arcadeSeatRelease([], 'kb'), [null, null, null, null], '释放空表 → 全空')
const cRel = __arcadeSeatRelease(c, 'pad:0')
eq(__arcadeSeatSlot(cRel, 'peer:zzzz9999'), 1, '释放后空位让旁观者可投影')

console.log('\n=== G) 输入健壮性 ===')
eq(__arcadeSeatClaim(null, 'kb', 'start'), ['kb', null, null, null], 'claim=null 也能用')
eq(__arcadeSeatPlan(null, ['kb']), { 0: 'kb' }, 'plan 的 claim=null 也能用')
eq(__arcadeSeatClaim([], null, 'start'), [null, null, null, null], 'dev=null → 不认领')
eq(__arcadeSeatClaim(['a', 'b', 'c'], 'd', 'start'), ['a', 'b', 'c', 'd'], '3 元素 claim 自动补到 4')
eq(__arcadeSeatClaim(['a', 'b', 'c', 'd', 'e'], 'f', 'start'), ['a', 'b', 'c', 'd'], '超长 claim 截到 4')

console.log('\n=========================')
console.log(fail === 0 ? `ALL PASS (${pass} 断言)` : `${fail} 失败 / ${pass} 通过`)
process.exit(fail === 0 ? 0 : 1)
