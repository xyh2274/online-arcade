// [patch] combo 单测：从产物里切出「线上真正在跑的那段 router IIFE」，桩化环境直接跑。
//
// 覆盖：平台门控（arcade 才生效、psx 绝不动）／展开表／键盘+远端路径（mapOf）／
//       真实手柄路径（comboPad，含「绝不污染真实手柄 buttons」这条硬约束）／开关与自定义表／
//       platforms 侧的面板行（LT/RT 必须真的出现在街机按键池里）。
//
// 用法: node test_combo.js
const fs = require('fs')
const path = require('path')

const SRC = path.join(__dirname, 'Player-BwKb4RpM.js')
const text = fs.readFileSync(SRC, 'utf8')
const PLAT = fs.readFileSync(path.join(__dirname, 'platforms-remote.js'), 'utf8')

// ---------- 切 IIFE：逐个 "\n})();" 截断试编译，第一个能过编译的才是正确闭合点 ----------
function sliceIIFE(src, from) {
  const re = /\n\}\)\(\);/g
  re.lastIndex = from
  let m
  while ((m = re.exec(src))) {
    const code = src.slice(from, m.index + m[0].length)
    try { new Function(code); return code } catch (e) { /* 还没到真正的结尾 */ }
  }
  throw new Error('找不到可编译的闭合点')
}

const start = text.indexOf('/* [patch] router')
if (start < 0) throw new Error('产物里找不到 [patch] router')
const iife = sliceIIFE(text, start)

// 切到的必须含本次改动特征，否则测试是假绿
if (!iife.includes('[patch] combo')) throw new Error('router 里没有 [patch] combo —— 补丁没打上')
if (!iife.includes('q.buttons = comboPad(q, p)')) throw new Error('真实手柄透传没改成 comboPad —— 组合键对手柄无效')
if (!/COMBO_LOG = \{ l2: \['b', 'y'\], r2: \['a', 'x'\] \}/.test(iife)) throw new Error('组合表不是预期内容')
if (!/comboKeys: function/.test(iife) || !/comboPad: function/.test(iife)) throw new Error('调试出口不在')

// ---------- 桩化环境 ----------
function makeEnv(opts) {
  opts = opts || {}
  const store = Object.assign({}, opts.ls)
  const localStorage = {
    getItem: (k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v) },
    removeItem: (k) => { delete store[k] },
    key: (i) => Object.keys(store)[i],
    get length() { return Object.keys(store).length },
  }
  const nav = { getGamepads: () => [], webkitGetGamepads: null }
  const doc = {
    createElement: () => ({ className: '', style: {}, innerHTML: '', offsetWidth: 0, appendChild() { } }),
    body: { appendChild() { } },
    documentElement: { appendChild() { } },
    addEventListener() { }, removeEventListener() { },
  }
  const win = { addEventListener() { } }
  const g = { console: console }
  if (opts.platform) g.__arcadeKeyPlatform = opts.platform

  const seat = {
    __arcadeSeatClaim: (claim) => claim.slice(),
    __arcadeSeatRelease: (claim) => claim.slice(),
    __arcadeSeatPlan: () => ({}),
  }
  const fn = new Function('globalThis', 'navigator', 'localStorage', 'document', 'window',
    '__arcadeSeatClaim', '__arcadeSeatRelease', '__arcadeSeatPlan', iife)
  fn(g, nav, localStorage, doc, win, seat.__arcadeSeatClaim, seat.__arcadeSeatRelease, seat.__arcadeSeatPlan)
  if (!g.__arcadeRouter) throw new Error('router IIFE 没跑起来')
  return { g, localStorage, R: g.__arcadeRouter }
}

// 17 格标准手柄；press 形如 {6:1} 表示第 6 号按下（值 1）
function fakePad(press) {
  const b = []
  for (let i = 0; i < 17; i++) b.push({ pressed: false, touched: false, value: 0 })
  for (const k in (press || {})) {
    const i = Number(k)
    b[i].pressed = true; b[i].touched = true; b[i].value = press[k]
  }
  return { id: 'FakePad', index: 0, connected: true, mapping: 'standard', axes: [0, 0, 0, 0, 0, 0], buttons: b }
}
const num = (o) => Object.keys(o).map(Number).filter((n) => o[n]).sort((a, b) => a - b)

let pass = 0, fail = 0
function eq(actual, expected, msg) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected)
  if (a === e) { pass++; return }
  fail++
  console.log('  ✗ ' + msg + '\n      期望 ' + e + '\n      实际 ' + a)
}
function is(a, b, msg) {
  if (a === b) { pass++; return }
  fail++
  console.log('  ✗ ' + msg + '\n      期望 ' + (b ? '同一对象/true' : '不同对象/false') + '\n      实际 ' + (a ? '同一对象/true' : '不同对象/false'))
}

// ================= 1. 平台门控：只有街机能开 ----------
console.log('1. 平台门控')
let env = makeEnv({ platform: 'arcade' })
eq(!!env.R.combo(), true, 'arcade → 组合键启用')
env.g.__arcadeKeyPlatform = 'psx'
eq(env.R.combo(), null, 'psx → 关闭（L2/R2 是真扳机，绝不能动）')
env.g.__arcadeKeyPlatform = 'nes'
eq(env.R.combo(), null, 'nes → 关闭')
env.g.__arcadeKeyPlatform = undefined
eq(env.R.combo(), null, '平台未知（没进游戏）→ 关闭')
env.g.__arcadeKeyPlatform = 'neogeo'
eq(!!env.R.combo(), true, 'neogeo → 启用')

// ================= 2. 展开表 ----------
console.log('2. 展开表')
env = makeEnv({ platform: 'arcade' })
eq(env.R.combo().log, { l2: ['b', 'y'], r2: ['a', 'x'] }, '逻辑层：LT→(b,y)、RT→(a,x)')
eq(env.R.combo().idx, { 6: [0, 2], 7: [1, 3] }, '按钮层：LT(6)→[0(A),2(X)]、RT(7)→[1(B),3(Y)]')
console.log('   说明：0=A 1=B 2=X 3=Y；街机端口 A→A、B→B、X→C、Y→D ⇒ 双手=NeoGeo A+C、双腿=B+D')

// ================= 3. 键盘 / 远端路径（mapOf）----------
console.log('3. 键盘/远端路径')
eq(num(env.R.comboKeys({ l2: true })), [0, 2], 'LT 按下 → 同时点亮 0+2')
eq('6' in env.R.comboKeys({ l2: true }), false, 'LT 自己（6）被吃掉，不下发')
eq(num(env.R.comboKeys({ r2: true })), [1, 3], 'RT 按下 → 同时点亮 1+3')
eq('7' in env.R.comboKeys({ r2: true }), false, 'RT 自己（7）被吃掉')
eq(num(env.R.comboKeys({ l2: true, a: true })), [0, 1, 2], 'LT + 真按了 a ⇒ 0,1,2（a 自己的 1 不丢）')
eq(num(env.R.comboKeys({ l2: true, b: true })), [0, 2], 'LT + 真按了 b ⇒ 仍在 0,2（重复不叠加）')
eq(num(env.R.comboKeys({ up: true, l2: true })), [0, 2, 12], '方向键与组合键互不干扰')
eq(num(env.R.comboKeys({})), [], '什么都没按 → 空（但键存在）')
eq(num(env.R.comboKeys({ l2: false })), [], 'l2=false 不触发')

// ================= 4. 真实手柄路径（comboPad）----------
console.log('4. 真实手柄路径')
let p = fakePad({ 6: 1 })
let d = env.R.comboPad(p)
eq([d[0].pressed, d[2].pressed], [true, true], '按 LT(6) → 输出按下 0(A) 和 2(X)')
eq(d[6].pressed, false, 'LT(6) 本身被吃掉（否则核心 ABC 宏会叠进来）')
eq([d[0].value, d[2].value], [1, 1], '展开出来的键 value=1')

p = fakePad({ 7: 1 })
d = env.R.comboPad(p)
eq([d[1].pressed, d[3].pressed], [true, true], '按 RT(7) → 输出按下 1(B) 和 3(Y)')
eq(d[7].pressed, false, 'RT(7) 本身被吃掉')

p = fakePad({ 6: 1 })
d = env.R.comboPad(p)
eq(p.buttons[6].pressed, true, '★ 真实手柄原数组未被改写（LT 仍是按下状态）')
eq(p.buttons[0].pressed, false, '★ 真实手柄原数组未被改写（没有凭空多出 A）')
is(d === p.buttons, false, '街机启用时返回的是自持数组，不是真实手柄数组')

// 模拟扳机值保留 + 不误伤其它键
p = fakePad({ 4: 1 })
p.buttons[4].value = 0.42
d = env.R.comboPad(p)
eq(d[4].value, 0.42, '非组合键保留模拟量（L 的 0.42 不被抹成 1）')

// 组合键与真按键同时按
p = fakePad({ 0: 1, 6: 1 })
d = env.R.comboPad(p)
eq([d[0].pressed, d[2].pressed], [true, true], 'A 与 LT 同时按：0 仍是按下、2 被点亮')

// 没按组合键时不动
p = fakePad({ 0: 1 })
d = env.R.comboPad(p)
eq(num(Object.assign({}, { 0: d[0].pressed, 2: d[2].pressed, 6: d[6].pressed, 7: d[7].pressed })), [0], '只按 A：不凭空产生 2/6/7')

// 非街机平台：原样透传同一个数组对象
env.g.__arcadeKeyPlatform = 'psx'
p = fakePad({ 6: 1 })
d = env.R.comboPad(p)
is(d === p.buttons, true, 'psx → 直接返回真实手柄数组（零改动）')
eq(d[6].pressed, true, 'psx 的 L2 照旧（真扳机不能被吃）')
eq(d[0].pressed, false, 'psx 不会凭空多出 A')
env.g.__arcadeKeyPlatform = 'arcade'

// ================= 5. 开关与自定义表 ----------
console.log('5. 开关与自定义表')
env = makeEnv({ platform: 'arcade', ls: { 'arcade-combo': '0' } })
eq(env.R.combo(), null, "localStorage['arcade-combo']='0' → 关掉")
p = fakePad({ 6: 1 })
is(env.R.comboPad(p) === p.buttons, true, '关掉后手柄原样透传')

env = makeEnv({ platform: 'arcade', ls: { 'arcade-combo-table': '{"l2":["a","b"]}' } })
eq(env.R.combo().idx, { 6: [1, 0] }, 'localStorage 自定义表生效（LT→B+A）')
eq('r2' in env.R.combo().log, false, '自定义表里没写的键就不启用')

env = makeEnv({ platform: 'arcade' })
env.g.__arcadeComboTable = { l2: ['y'] }
eq(env.R.combo().idx, { 6: [2] }, '运行时 __arcadeComboTable 覆盖生效')
env.g.__arcadeComboTable = { l2: ['nope'], r2: [123] }
eq(env.R.combo(), null, '非法目标（不存在的逻辑键/非字符串）→ 整表作废，不启用')

// ================= 6. platforms 侧：面板要真的出现 LT/RT ----------
console.log('6. platforms 面板行')
const mi = PLAT.indexOf('f={arcade:')
const seg = PLAT.slice(mi, mi + 130)
eq(seg.includes('"l2","r2"'), true, '街机按键池里有 l2/r2（否则面板里看不到 LT/RT）')
eq(PLAT.includes('l2:"LT-双手"') && PLAT.includes('r2:"RT-双腿"'), true, '街机标签是 LT-双手 / RT-双腿')
eq(PLAT.includes('/*[patch] combo*/'), true, 'platforms 侧补丁标记在')
eq(PLAT.slice(PLAT.indexOf('g={arcade:'), PLAT.indexOf('g={arcade:') + 150).includes('psx'), false,
  '没有误改到 psx 的标签')
eq(/psx:\{a:"◯",b:"✕",x:"△",y:"□",l:"L1",r:"R1",l2:"L2",r2:"R2"\}/.test(PLAT), true, 'psx 标签原样保留')

console.log('\n' + (fail ? '失败 ' + fail + ' 条 / ' : '') + '通过 ' + pass + ' 条断言')
process.exit(fail ? 1 : 0)
